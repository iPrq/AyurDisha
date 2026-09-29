"""Intent + entity decoder for the formulation assistant.

Deterministic rules (and slash commands) run first; the structured LLM decoder is used only when
rules cannot classify the request. Decoder output is a proposal — ``planner`` decides what happens.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from graph.formulation.extraction import _num_in_text, _term_in_text, rules_extract
from graph.formulation.models import AgentIntent, FormulationContext, GraphFilter
from graph.prompts import INTENT_DECODER_SYSTEM
from llm.structured import structured_invoke

logger = logging.getLogger(__name__)


class DecodedIngredient(BaseModel):
    name: str
    operation: Literal["add", "remove", "update", "focus"] = "add"
    quantity: float | None = None
    unit: str | None = None
    plant_part: str | None = None


class DecodedRequest(BaseModel):
    intents: list[AgentIntent] = Field(default_factory=list)
    ingredients: list[DecodedIngredient] = Field(default_factory=list)
    name: str | None = None
    dosage_form: str | None = None
    route: str | None = None
    intended_use: str | None = None
    claims: list[str] = Field(default_factory=list)
    target_market: str | None = None
    purpose: str | None = None
    entity_type: str | None = None
    resource_source: str | None = None
    graph_filter: GraphFilter | None = None
    resolve_choice: str | None = Field(default=None, description="Botanical name chosen for an ambiguous term")
    navigate_only: bool = Field(default=False, description="Open the tool without starting an analysis")


class DecodeOutcome(BaseModel):
    request: DecodedRequest
    decoder: Literal["llm", "rules", "command"]


SLASH_COMMANDS: dict[str, list[AgentIntent]] = {
    "/review": [AgentIntent.REVIEW_PRODUCT],
    "/patent": [AgentIntent.ANALYZE_PATENT],
    "/abs": [AgentIntent.CHECK_ABS],
    "/evidence": [AgentIntent.VIEW_EVIDENCE],
    "/formulation": [AgentIntent.SHOW_FORMULATION],
    "/map": [AgentIntent.SHOW_FORMULATION],
    "/compare": [AgentIntent.COMPARE_FORMULATIONS],
}

_INTENT_PATTERNS: list[tuple[AgentIntent, re.Pattern[str]]] = [
    (AgentIntent.SCENARIO, re.compile(r"\bwhat if\b|\bsuppose\b|\bhypothetical", re.I)),
    (AgentIntent.COMPARE_FORMULATIONS, re.compile(r"\bcompare\b|\bprevious version\b|\bdiff\b|\bwhat changed\b", re.I)),
    (AgentIntent.SHOW_DECISION_PATH, re.compile(r"\bwhy (?:is|does) (?:abs|patent|it|this)\b.*\b(?:relevant|apply|matter)|\bdecision path\b", re.I)),
    (AgentIntent.VIEW_EVIDENCE, re.compile(r"\bevidence\b|\bsources?\b|\bwhy (?:is|does)\b|\bexplain why\b|\bwhy this matters\b", re.I)),
    (AgentIntent.RESOLVE_AMBIGUITY, re.compile(r"\bresolve\b|\bi mean\b|\bambigu", re.I)),
    (AgentIntent.SHOW_FORMULATION, re.compile(r"\b(?:show|open)\b.*\b(?:formulation|map|graph)\b|\bformulation map\b", re.I)),
    (AgentIntent.UPLOAD_DOCUMENT, re.compile(r"\b(?:this|the|my)\s+pdf\b|\bupload\b", re.I)),
    (AgentIntent.REVIEW_PRODUCT, re.compile(r"\bproduct review\b|\breview (?:this|the|my)?\s*product\b|\breview it\b|\bcan (?:it|this|i) be sold\b|\bsell (?:it|this)\b|\bmarket feasibility\b|\bcomplian", re.I)),
    (AgentIntent.ANALYZE_PATENT, re.compile(r"\bpatent", re.I)),
    (AgentIntent.CHECK_ABS, re.compile(r"\babs\b|\bnba\b|\bbenefit[- ]shar|\bbiodiversity\b", re.I)),
]
_REMOVE_RE = re.compile(r"\b(?:remove|delete|drop|take out)\b", re.I)
_UPDATE_RE = re.compile(r"\b(?:change|set|make|update|increase|decrease|reduce|raise)\b", re.I)
_ADD_RE = re.compile(r"\b(?:add|include|create|build|want|with|make a|formulat|containing|contains)\b", re.I)
_PRONOUN_RE = re.compile(r"\b(?:it|that|this one)\b", re.I)
_ACTION_VERB_RE = re.compile(
    r"\b(?:check|run|analy[sz]e|assess|review|can i|could i|do i need|start|calculate|is it patentable)\b", re.I
)
_NAVIGATE_RE = re.compile(r"\b(?:open|go to|take me to|navigate to|switch to)\b", re.I)
_GRAPH_VIEW_RE = re.compile(
    r"\bshow\b.*\b(patent|abs|regulatory|evidence)\b[- ]?(?:related\s+)?(?:information|info|branch|nodes|path|details)\b",
    re.I,
)
TOOL_INTENTS = (AgentIntent.REVIEW_PRODUCT, AgentIntent.ANALYZE_PATENT, AgentIntent.CHECK_ABS)
_QTY_ONLY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|kg|ml|%)\b", re.I)

_PURPOSES = [
    ("commercial_utilization", re.compile(r"\bcommercial", re.I)),
    ("research", re.compile(r"\bresearch\b", re.I)),
    ("bio_survey", re.compile(r"\bbio[- ]?survey", re.I)),
    ("ipr", re.compile(r"\bipr\b|\bfor (?:a )?patent (?:purpose|filing)", re.I)),
]


def _first_pos(pattern: re.Pattern[str], text: str) -> int:
    m = pattern.search(text)
    return m.start() if m else -1


def _mentioned_context_ingredients(text: str, ctx: FormulationContext | None) -> list[tuple[int, str]]:
    if ctx is None:
        return []
    found: list[tuple[int, str]] = []
    low = text.lower()
    for ing in ctx.ingredients:
        names = [
            ing.user_term,
            *([ing.normalized_name] if ing.normalized_name else []),
            *([ing.botanical_name] if ing.botanical_name else []),
            *ing.synonyms,
        ]
        for name in names:
            m = re.search(rf"(?<![\w-]){re.escape(name.lower())}(?![\w-])", low)
            if m:
                found.append((m.start(), ing.user_term))
                break
    return found


def rules_decode(text: str, ctx: FormulationContext | None) -> DecodeOutcome:
    raw = (text or "").strip()
    first = raw.split()[0].lower() if raw else ""
    if first in SLASH_COMMANDS:
        return DecodeOutcome(request=DecodedRequest(intents=list(SLASH_COMMANDS[first])), decoder="command")

    extracted = rules_extract(raw)
    positions: list[tuple[int, AgentIntent]] = []
    for intent, pattern in _INTENT_PATTERNS:
        pos = _first_pos(pattern, raw)
        if pos >= 0:
            positions.append((pos, intent))

    req = DecodedRequest()
    req.dosage_form = extracted.dosage_form or None
    req.route = extracted.route or None
    req.intended_use = extracted.intended_use or None
    req.name = extracted.name or None

    remove_pos = _first_pos(_REMOVE_RE, raw)
    update_pos = _first_pos(_UPDATE_RE, raw)
    scenario = any(i == AgentIntent.SCENARIO for _, i in positions)

    # Ingredients from the lexicon / quantity patterns, plus names already in the context.
    mentions: dict[str, DecodedIngredient] = {}
    for ing in extracted.ingredients:
        mentions[ing.user_term.lower()] = DecodedIngredient(
            name=ing.user_term, quantity=ing.quantity, unit=ing.unit, plant_part=ing.plant_part
        )
    for _, term in _mentioned_context_ingredients(raw, ctx):
        already = any(
            (found := ctx.find_ingredient(d.name)) is not None and found.user_term == term
            for d in mentions.values()
        ) if ctx else False
        if not already and term.lower() not in mentions:
            mentions[term.lower()] = DecodedIngredient(name=term)
    if ctx is not None:
        for key, d in list(mentions.items()):
            existing = ctx.find_ingredient(d.name)
            if existing and d.quantity is None:
                qm = re.search(re.escape(d.name) + r"\D{0,20}?(\d+(?:\.\d+)?)\s*(mg|mcg|g|kg|ml|%)\b", raw, re.I)
                if qm:
                    d.quantity, d.unit = float(qm.group(1)), qm.group(2).lower()

    # Pronoun reference ("make it 500 mg") → last referenced ingredient.
    if not mentions and ctx is not None and ctx.last_referenced_ingredient and _PRONOUN_RE.search(raw):
        qm = _QTY_ONLY_RE.search(raw)
        ref = next((i for i in ctx.ingredients if i.id == ctx.last_referenced_ingredient), None)
        if ref is not None and qm:
            mentions[ref.user_term.lower()] = DecodedIngredient(
                name=ref.user_term, operation="update", quantity=float(qm.group(1)), unit=qm.group(2).lower()
            )

    for d in mentions.values():
        existing = ctx.find_ingredient(d.name) if ctx else None
        if remove_pos >= 0 and not scenario:
            d.operation = "remove"
        elif existing is not None and (d.quantity is not None or d.plant_part):
            d.operation = "update"
        elif existing is not None and re.search(r"\b(?:add|include)\b", raw, re.I):
            d.operation = "add"
        elif existing is not None:
            d.operation = "focus"
        elif update_pos >= 0 and _ADD_RE.search(raw) is None:
            d.operation = "update"
        else:
            d.operation = "add"
    req.ingredients = list(mentions.values())

    for value, pattern in _PURPOSES:
        if pattern.search(raw):
            req.purpose = value
            break
    if re.search(r"\bforeign\b", raw, re.I):
        req.entity_type = "foreign"
    elif re.search(r"\bindian (?:company|entity|firm|startup|applicant)\b", raw, re.I):
        req.entity_type = "indian"
    if re.search(r"\bcultivated\b", raw, re.I):
        req.resource_source = "cultivated"
    elif re.search(r"\bwild\b", raw, re.I):
        req.resource_source = "wild"

    intents: list[AgentIntent] = []
    ops = {d.operation for d in req.ingredients}
    if scenario:
        intents.append(AgentIntent.SCENARIO)
    else:
        if "add" in ops:
            intents.append(AgentIntent.CREATE_FORMULATION if ctx is None or not ctx.ingredients else AgentIntent.ADD_INGREDIENT)
        if "remove" in ops:
            intents.append(AgentIntent.REMOVE_INGREDIENT)
        if "update" in ops:
            intents.append(AgentIntent.UPDATE_QUANTITY)
        if req.dosage_form and (ctx is None or ctx.dosage_form != req.dosage_form):
            intents.append(AgentIntent.UPDATE_DOSAGE_FORM)
        if req.intended_use and (ctx is None or ctx.intended_use != req.intended_use):
            intents.append(AgentIntent.UPDATE_INTENDED_USE)
        if remove_pos >= 0 and not req.ingredients:
            intents.append(AgentIntent.REMOVE_INGREDIENT)
    for _, intent in sorted(positions, key=lambda p: p[0]):
        if intent == AgentIntent.SCENARIO or intent in intents:
            continue
        if intent == AgentIntent.RESOLVE_AMBIGUITY and not req.ingredients and ctx is None:
            continue
        intents.append(intent)
    if "focus" in ops and not any(
        i in intents for i in (AgentIntent.VIEW_EVIDENCE, AgentIntent.RESOLVE_AMBIGUITY, AgentIntent.SHOW_DECISION_PATH)
    ):
        if re.search(r"\bshow\b|\bfocus\b|\bwhere\b", raw, re.I):
            intents.append(AgentIntent.FOCUS_ENTITY)

    view = _GRAPH_VIEW_RE.search(raw)
    if view and AgentIntent.SHOW_DECISION_PATH not in intents:
        intents.append(AgentIntent.SHOW_DECISION_PATH)
    if AgentIntent.SHOW_DECISION_PATH in intents:
        if view:
            req.graph_filter = view.group(1).lower()  # type: ignore[assignment]
        elif re.search(r"\babs\b|\bbiodiversity\b", raw, re.I):
            req.graph_filter = "abs"
        elif re.search(r"patent", raw, re.I):
            req.graph_filter = "patent"
    # "Why is ABS relevant?" / "show patent info" are graph views, not tool runs.
    has_action_verb = bool(_ACTION_VERB_RE.search(raw))
    if AgentIntent.SHOW_DECISION_PATH in intents or (
        AgentIntent.VIEW_EVIDENCE in intents and not has_action_verb
    ):
        intents = [i for i in intents if i not in TOOL_INTENTS]
    if any(i in intents for i in TOOL_INTENTS) and _NAVIGATE_RE.search(raw) and not has_action_verb:
        req.navigate_only = True
    if AgentIntent.RESOLVE_AMBIGUITY in intents and ctx is not None:
        for ing in ctx.ingredients:
            for c in ing.candidates:
                if c.botanical_name.lower() in raw.lower():
                    req.resolve_choice = c.botanical_name
    if not intents:
        intents = [AgentIntent.GENERAL_QUESTION]
    req.intents = intents
    return DecodeOutcome(request=req, decoder="rules")


def _context_summary(ctx: FormulationContext | None) -> str:
    if ctx is None:
        return "No current formulation."
    ings = ", ".join(
        f"{i.user_term}" + (f" {i.quantity:g} {i.unit or ''}" if i.quantity is not None else "")
        for i in ctx.ingredients
    ) or "none"
    last = next((i.user_term for i in ctx.ingredients if i.id == ctx.last_referenced_ingredient), None)
    return (
        f"Current formulation: ingredients=[{ings}]; dosage_form={ctx.dosage_form or 'unknown'}; "
        f"intended_use={ctx.intended_use or 'unknown'}; last_referenced_ingredient={last or 'none'}"
    )


def _validate_llm(req: DecodedRequest, text: str, ctx: FormulationContext | None) -> DecodedRequest:
    """Drop entities that do not appear in the user text or the current formulation."""
    kept: list[DecodedIngredient] = []
    for d in req.ingredients:
        in_ctx = ctx is not None and ctx.find_ingredient(d.name) is not None
        if not (_term_in_text(d.name, text) or in_ctx):
            continue
        if d.quantity is not None and not _num_in_text(d.quantity, text):
            d.quantity, d.unit = None, None
        kept.append(d)
    req.ingredients = kept
    for field in ("dosage_form", "route", "name", "target_market"):
        val = getattr(req, field)
        if val and not _term_in_text(val.split()[0], text):
            setattr(req, field, None)
    for field in ("purpose", "entity_type", "resource_source"):
        val = getattr(req, field)
        if val and not _term_in_text(val.split("_")[0], text):
            setattr(req, field, None)
    return req


def decode_request(text: str, ctx: FormulationContext | None, *, llm: Any | None = None) -> DecodeOutcome:
    rules = rules_decode(text, ctx)
    if rules.decoder == "command" or llm is None or rules.request.intents != [AgentIntent.GENERAL_QUESTION]:
        return rules
    try:
        req = structured_invoke(
            llm,
            DecodedRequest,
            system=INTENT_DECODER_SYSTEM,
            user=f"{_context_summary(ctx)}\n\nUser request:\n{text}",
        )
    except Exception:  # noqa: BLE001 - rules result stands
        logger.warning("intent LLM decode failed; using rules", exc_info=True)
        return rules
    req = _validate_llm(req, text, ctx)
    if not req.intents:
        req.intents = [AgentIntent.GENERAL_QUESTION]
    return DecodeOutcome(request=req, decoder="llm")
