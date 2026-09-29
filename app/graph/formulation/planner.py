"""State-aware action planner: decoded request + current formulation → validated AgentPlan.

Only predefined action types can be emitted; every action is re-validated by Pydantic.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import TypeAdapter

from graph.formulation.clarify import ENTITY_OPTIONS, PURPOSE_OPTIONS
from graph.formulation.intent import TOOL_INTENTS, DecodedRequest
from graph.formulation.models import (
    UNITS,
    AgentAction,
    AgentIntent,
    AgentPlan,
    ClarificationOption,
    ClarificationRequest,
    FormulationContext,
    IdentityStatus,
    PlannedAction,
    executor_for,
)

_ACTION_ADAPTER: TypeAdapter[Any] = TypeAdapter(AgentAction)

TOOL_ROUTES = {
    AgentIntent.REVIEW_PRODUCT: ("/review", "review", "RUN_PRODUCT_REVIEW", "Product Review", "Running product review"),
    AgentIntent.ANALYZE_PATENT: ("/patent", "patent", "RUN_PATENT_ADVISOR", "Patent Advisor", "Running patent analysis"),
    AgentIntent.CHECK_ABS: ("/nba-abs", "nba-abs", "RUN_ABS", "NBA / ABS", "Assessing biodiversity/ABS applicability"),
}
_FIELD_VALUES = {
    "purpose": {o.value for o in PURPOSE_OPTIONS},
    "entity_type": {o.value for o in ENTITY_OPTIONS},
    "resource_source": {"wild", "cultivated", "unknown"},
}


def _fmt_qty(q: float | None, unit: str | None) -> str:
    if q is None:
        return ""
    return f"{int(q) if float(q).is_integer() else q} {unit or ''}".strip()


class _Plan:
    def __init__(self) -> None:
        self.actions: list[PlannedAction] = []
        self.notes: list[str] = []

    def add(self, label: str, **payload: Any) -> None:
        action = _ACTION_ADAPTER.validate_python(payload)
        self.actions.append(
            PlannedAction(
                id=f"a{len(self.actions) + 1}_{uuid.uuid4().hex[:6]}",
                label=label,
                executor=executor_for(action.type),
                action=action,
            )
        )

    def has(self, action_type: str) -> bool:
        return any(a.action.type == action_type for a in self.actions)


def _unit(unit: str | None) -> str | None:
    u = (unit or "").lower() or None
    return u if u in UNITS else None


def plan_request(
    decoded: DecodedRequest,
    ctx: FormulationContext | None,
    *,
    text: str,
    current_route: str | None = None,
) -> AgentPlan:
    p = _Plan()
    intents = list(decoded.intents) or [AgentIntent.GENERAL_QUESTION]
    primary = intents[0]
    on_formulation = (current_route or "").startswith("/formulation")
    clarification: ClarificationRequest | None = None

    def ensure_formulation_page() -> None:
        if not on_formulation and not p.has("NAVIGATE"):
            p.add("Opening Formulation Intelligence", type="NAVIGATE", route="/formulation")

    # -- Scenario: never mutates the formulation ------------------------------
    if AgentIntent.SCENARIO in intents:
        changes = []
        for d in decoded.ingredients:
            ing = ctx.find_ingredient(d.name) if ctx else None
            if ing is None:
                p.notes.append(f"I don't see {d.name} in the current formulation, so I can't model that change.")
                continue
            if d.quantity is None:
                p.notes.append(f"Tell me the new quantity for {ing.user_term} to model the scenario.")
                continue
            changes.append({"ingredient_id": ing.id, "quantity": d.quantity, "unit": _unit(d.unit) or ing.unit})
        if changes:
            ensure_formulation_page()
            p.add("Creating scenario (not a determination)", type="CREATE_SCENARIO", changes=changes)
        return _finish(p, decoded, AgentIntent.SCENARIO, intents, text, None)

    if AgentIntent.COMPARE_FORMULATIONS in intents:
        if ctx is None or ctx.version < 2:
            p.notes.append("There is no previous version of this formulation to compare yet.")
        else:
            ensure_formulation_page()
            p.add("Comparing with the previous version", type="COMPARE_VERSIONS")

    # -- Formulation mutations -------------------------------------------------
    adds = [d for d in decoded.ingredients if d.operation == "add"]
    needs_ctx = bool(adds) or AgentIntent.CREATE_FORMULATION in intents
    if ctx is None and needs_ctx:
        p.add(
            f"Creating formulation{f' “{decoded.name}”' if decoded.name else ''}",
            type="CREATE_FORMULATION",
            name=decoded.name,
        )
    elif ctx is not None and decoded.name and decoded.name != ctx.name:
        p.add(f"Setting name: {decoded.name}", type="UPDATE_FIELD", field="name", value=decoded.name)

    planned_terms: set[str] = set()
    focus_terms: list[str] = []
    mutated = False
    for d in decoded.ingredients:
        existing = ctx.find_ingredient(d.name) if ctx else None
        unit = _unit(d.unit)
        if d.operation == "add":
            if d.name.lower() in planned_terms:
                continue
            if existing is not None:
                if d.quantity is not None and (existing.quantity, existing.unit) != (d.quantity, unit or existing.unit):
                    p.add(
                        f"Set quantity: {existing.user_term} {_fmt_qty(d.quantity, unit or existing.unit)}",
                        type="UPDATE_INGREDIENT", ingredient_id=existing.id, quantity=d.quantity,
                        unit=unit or existing.unit,
                    )
                    mutated = True
                else:
                    p.notes.append(f"{existing.user_term} is already in the formulation.")
                continue
            planned_terms.add(d.name.lower())
            qty = _fmt_qty(d.quantity, unit)
            p.add(
                f"Add {d.name}" + (f" — {qty}" if qty else ""),
                type="ADD_INGREDIENT", user_term=d.name, quantity=d.quantity, unit=unit, plant_part=d.plant_part,
            )
            mutated = True
        elif d.operation == "remove":
            if existing is None:
                p.notes.append(f"I don't see {d.name} in the current formulation.")
                continue
            p.add(f"Remove {existing.user_term}", type="REMOVE_INGREDIENT", ingredient_id=existing.id)
            mutated = True
        elif d.operation == "update":
            if existing is None:
                p.notes.append(f"I don't see {d.name} in the current formulation.")
                continue
            if d.quantity is None and not d.plant_part:
                continue
            changes = {}
            if d.quantity is not None:
                changes["quantity"] = d.quantity
                changes["unit"] = unit or existing.unit
            if d.plant_part:
                changes["plant_part"] = d.plant_part
            label = (
                f"Set quantity: {existing.user_term} {_fmt_qty(d.quantity, changes.get('unit'))}"
                if d.quantity is not None else f"Set plant part: {existing.user_term} {d.plant_part}"
            )
            p.add(label, type="UPDATE_INGREDIENT", ingredient_id=existing.id, **changes)
            mutated = True
        elif d.operation == "focus":
            focus_terms.append(existing.user_term if existing else d.name)

    if AgentIntent.REMOVE_INGREDIENT in intents and not decoded.ingredients:
        p.notes.append("Which ingredient should I remove?")

    if decoded.dosage_form and (ctx is None or ctx.dosage_form != decoded.dosage_form.lower()) and (ctx or needs_ctx):
        p.add(f"Set dosage form: {decoded.dosage_form.title()}", type="UPDATE_DOSAGE_FORM", value=decoded.dosage_form)
        mutated = True
    if decoded.route and (ctx is None or ctx.route != decoded.route) and (ctx or needs_ctx):
        p.add(f"Set route: {decoded.route}", type="UPDATE_FIELD", field="route", value=decoded.route)
        mutated = True
    if decoded.intended_use and (ctx is None or ctx.intended_use != decoded.intended_use) and (ctx or needs_ctx):
        p.add(f"Set intended use: {decoded.intended_use}", type="UPDATE_INTENDED_USE", value=decoded.intended_use)
        mutated = True
    if decoded.claims and (ctx or needs_ctx):
        p.add(f"Record {len(decoded.claims)} claim(s)", type="UPDATE_CLAIMS", claims=decoded.claims)
        mutated = True
    for field in ("purpose", "entity_type", "resource_source"):
        value = getattr(decoded, field)
        if value and value in _FIELD_VALUES[field] and (ctx or needs_ctx):
            current = getattr(ctx, field, None) if ctx else None
            if (current.value if hasattr(current, "value") else current) != value:
                label = next(
                    (o.label for o in [*PURPOSE_OPTIONS, *ENTITY_OPTIONS] if o.value == value), value
                )
                p.add(f"Set {field.replace('_', ' ')}: {label}", type="UPDATE_FIELD", field=field, value=value)
                mutated = True

    # -- Ambiguity resolution ---------------------------------------------------
    if AgentIntent.RESOLVE_AMBIGUITY in intents and ctx is not None:
        targets = [
            i for i in ctx.ingredients
            if i.identity_status == IdentityStatus.AMBIGUOUS
            and (not focus_terms or i.user_term in focus_terms)
        ]
        if not targets:
            p.notes.append("There is no ambiguous ingredient in the current formulation.")
        else:
            ing = targets[0]
            if decoded.resolve_choice and any(
                c.botanical_name == decoded.resolve_choice for c in ing.candidates
            ):
                p.add(
                    f"Resolve {ing.user_term} as {decoded.resolve_choice}",
                    type="RESOLVE_ENTITY", ingredient_id=ing.id, botanical_name=decoded.resolve_choice,
                )
                mutated = True
            else:
                ensure_formulation_page()
                p.add(f"Focusing {ing.user_term}", type="FOCUS_GRAPH_NODE", ingredient_id=ing.id)
                clarification = ClarificationRequest(
                    kind="identity",
                    field="botanical_identity",
                    ingredient_id=ing.id,
                    question=f"“{ing.user_term}” can refer to more than one plant. Which one do you mean?",
                    options=[ClarificationOption(value=c.botanical_name, label=c.botanical_name) for c in ing.candidates],
                )
                p.add("Waiting for your choice", type="ASK_CLARIFICATION", clarification=clarification)

    tool_intents = [i for i in intents if i in TOOL_INTENTS]

    # Mutations without a tool run: show the updated map.
    if mutated and not tool_intents:
        ensure_formulation_page()
        p.add("Updating formulation map", type="ANALYZE_FORMULATION")

    # -- Graph navigation --------------------------------------------------------
    if AgentIntent.SHOW_FORMULATION in intents:
        ensure_formulation_page()
    if AgentIntent.SHOW_DECISION_PATH in intents:
        ensure_formulation_page()
        if decoded.graph_filter:
            p.add(f"Highlighting {decoded.graph_filter} path", type="SET_GRAPH_FILTER", filter=decoded.graph_filter)
        for term in focus_terms:
            p.add(f"Focusing {term}", type="FOCUS_GRAPH_NODE", term=term)
    if AgentIntent.FOCUS_ENTITY in intents:
        ensure_formulation_page()
        for term in focus_terms:
            p.add(f"Focusing {term}", type="FOCUS_GRAPH_NODE", term=term)
    if AgentIntent.VIEW_EVIDENCE in intents:
        ensure_formulation_page()
        if focus_terms:
            for term in focus_terms:
                p.add(f"Focusing {term}", type="FOCUS_GRAPH_NODE", term=term)
                p.add(f"Opening evidence for {term}", type="OPEN_EVIDENCE", term=term)
        else:
            p.add("Opening evidence", type="SET_GRAPH_FILTER", filter="evidence")
            p.add("Opening evidence panel", type="OPEN_EVIDENCE")

    # -- Tool hand-offs ------------------------------------------------------------
    if tool_intents and ctx is None and not needs_ctx:
        p.notes.append("There is no formulation yet. Tell me the ingredients first (for example, “Ashwagandha 500 mg capsule”).")
        tool_intents = []
    for intent in tool_intents:
        route, tool, run_type, title, run_label = TOOL_ROUTES[intent]
        p.add(f"Opening {title}", type="NAVIGATE", route=route)
        p.add("Importing formulation context", type="IMPORT_CONTEXT", tool=tool)
        if not decoded.navigate_only:
            p.add(run_label, type=run_type)

    if primary == AgentIntent.GENERAL_QUESTION and not p.actions:
        p.notes.append(
            "I can build and edit formulations, open Product Review, Patent Advisor or NBA / ABS with your "
            "formulation, and show evidence. I don't give legal conclusions myself — the analyses do, with sources."
        )
    return _finish(p, decoded, primary, intents, text, clarification)


def _explain(p: _Plan) -> str:
    mutations = [a for a in p.actions if a.executor == "server" and a.action.type != "CREATE_SCENARIO"]
    tool_opens = [a.label.removeprefix("Opening ") for a in p.actions if a.action.type == "NAVIGATE" and a.label != "Opening Formulation Intelligence"]
    parts: list[str] = []
    if mutations:
        parts.append("update the formulation")
    if tool_opens:
        parts.append(f"open {' and '.join(tool_opens)} with the updated context" if mutations else f"open {' and '.join(tool_opens)} with your formulation")
    if any(a.action.type == "CREATE_SCENARIO" for a in p.actions):
        parts.append("model the change as a scenario without changing your formulation")
    if not parts:
        return ""
    return "I'll " + ", then ".join(parts) + "."


def _finish(
    p: _Plan,
    decoded: DecodedRequest,
    primary: AgentIntent,
    intents: list[AgentIntent],
    text: str,
    clarification: ClarificationRequest | None,
) -> AgentPlan:
    message = " ".join(x for x in [_explain(p), *p.notes] if x)
    return AgentPlan(
        run_id=f"run_{uuid.uuid4().hex[:10]}",
        intent=primary,
        intents=intents,
        message=message,
        actions=p.actions,
        clarification=clarification,
        requires_confirmation=any(a.action.type == "REMOVE_INGREDIENT" for a in p.actions),
        original_text=text,
        normalized_text=text,
    )
