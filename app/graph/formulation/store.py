"""In-memory versioned formulation store + validated action execution.

User formulations live only here (process memory); they are never indexed into the legal corpus.
"""

from __future__ import annotations

import threading
import uuid
from typing import Any, Callable

from graph.formulation.identity import resolve_by_user_choice
from graph.formulation.models import (
    MUTATING_ACTIONS,
    ActionResult,
    FormulationContext,
    FormulationIngredient,
    FormulationSourceType,
    FormulationVersion,
    VersionComparison,
    utcnow,
)
from graph.models import AbsPurpose, EntityType, LegalScope, ResourceSource

IngredientResolver = Callable[[FormulationIngredient], FormulationIngredient]

MAX_VERSIONS = 50


class FormulationNotFound(KeyError):
    pass


class VersionConflict(RuntimeError):
    pass


class ActionRejected(ValueError):
    """Validated-but-inapplicable action (e.g. removing an ingredient that does not exist)."""


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _fmt_qty(quantity: float | None, unit: str | None) -> str:
    if quantity is None:
        return "no quantity"
    q = int(quantity) if float(quantity).is_integer() else quantity
    return f"{q} {unit or ''}".strip()


class FormulationStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._current: dict[str, FormulationContext] = {}
        self._history: dict[str, list[FormulationVersion]] = {}

    # -- basic access -----------------------------------------------------

    def create(self, context: FormulationContext | None = None, *, summary: str = "Created formulation") -> FormulationContext:
        with self._lock:
            ctx = context.model_copy(deep=True) if context else FormulationContext(formulation_id="")
            if not ctx.formulation_id:
                ctx.formulation_id = new_id("form")
            ctx.version = 1
            ctx.created_at = ctx.updated_at = utcnow()
            self._current[ctx.formulation_id] = ctx
            self._history[ctx.formulation_id] = [
                FormulationVersion(version=1, change_summary=summary, snapshot=ctx.model_copy(deep=True))
            ]
            return ctx.model_copy(deep=True)

    def get(self, formulation_id: str) -> FormulationContext:
        with self._lock:
            ctx = self._current.get(formulation_id)
            if ctx is None:
                raise FormulationNotFound(formulation_id)
            return ctx.model_copy(deep=True)

    def history(self, formulation_id: str) -> list[FormulationVersion]:
        with self._lock:
            if formulation_id not in self._history:
                raise FormulationNotFound(formulation_id)
            return [v.model_copy(deep=True) for v in self._history[formulation_id]]

    def version(self, formulation_id: str, version: int) -> FormulationContext:
        for v in self.history(formulation_id):
            if v.version == version:
                return v.snapshot
        raise FormulationNotFound(f"{formulation_id}@v{version}")

    def update_derived(self, ctx: FormulationContext) -> None:
        """Refresh computed fields on the current version (no new version: nothing the user changed)."""
        with self._lock:
            current = self._current.get(ctx.formulation_id)
            if current is None:
                raise FormulationNotFound(ctx.formulation_id)
            current.formulation_characteristics = [c.model_copy() for c in ctx.formulation_characteristics]
            current.missing_information = list(ctx.missing_information)
            current.evidence_ids = list(ctx.evidence_ids)
            if ctx.version == current.version:
                self._history[ctx.formulation_id][-1].snapshot = current.model_copy(deep=True)

    def replace(self, ctx: FormulationContext, *, summary: str, action_type: str | None = None) -> FormulationContext:
        """Commit a modified context as a new version."""
        with self._lock:
            if ctx.formulation_id not in self._current:
                raise FormulationNotFound(ctx.formulation_id)
            prev = self._current[ctx.formulation_id]
            ctx = ctx.model_copy(deep=True)
            ctx.version = prev.version + 1
            ctx.created_at = prev.created_at
            ctx.updated_at = utcnow()
            self._current[ctx.formulation_id] = ctx
            hist = self._history[ctx.formulation_id]
            hist.append(
                FormulationVersion(
                    version=ctx.version,
                    change_summary=summary,
                    action_type=action_type,
                    snapshot=ctx.model_copy(deep=True),
                )
            )
            del hist[:-MAX_VERSIONS]
            return ctx.model_copy(deep=True)

    # -- actions ------------------------------------------------------------

    def apply_action(
        self,
        formulation_id: str,
        action: Any,
        *,
        base_version: int | None = None,
        resolver: IngredientResolver | None = None,
    ) -> ActionResult:
        if action.type not in MUTATING_ACTIONS:
            raise ActionRejected(f"{action.type} is not a formulation state action.")
        with self._lock:
            ctx = self.get(formulation_id)
            if base_version is not None and base_version != ctx.version:
                raise VersionConflict(
                    f"Formulation changed (current v{ctx.version}, request based on v{base_version})."
                )
            summary, changed_id, fields = _mutate(ctx, action, resolver)
            committed = self.replace(ctx, summary=summary, action_type=action.type)
            return ActionResult(
                ok=True,
                action_type=action.type,
                summary=summary,
                context=committed,
                changed_ingredient_id=changed_id,
                changed_fields=fields,
            )

    def compare(self, formulation_id: str, from_version: int | None, to_version: int | None) -> VersionComparison:
        hist = self.history(formulation_id)
        to_v = to_version or hist[-1].version
        from_v = from_version or max(1, to_v - 1)
        a = self.version(formulation_id, from_v)
        b = self.version(formulation_id, to_v)
        return VersionComparison(
            formulation_id=formulation_id,
            from_version=from_v,
            to_version=to_v,
            changes=diff_contexts(a, b),
        )


def diff_contexts(a: FormulationContext, b: FormulationContext) -> list[str]:
    changes: list[str] = []
    a_ing = {i.id: i for i in a.ingredients}
    b_ing = {i.id: i for i in b.ingredients}
    for iid, ing in b_ing.items():
        if iid not in a_ing:
            changes.append(f"Added {ing.user_term} ({_fmt_qty(ing.quantity, ing.unit)})")
            continue
        old = a_ing[iid]
        if (old.quantity, old.unit) != (ing.quantity, ing.unit):
            changes.append(
                f"{ing.user_term}: {_fmt_qty(old.quantity, old.unit)} → {_fmt_qty(ing.quantity, ing.unit)}"
            )
        if old.user_term != ing.user_term:
            changes.append(f"Renamed {old.user_term} → {ing.user_term}")
        if old.plant_part != ing.plant_part:
            changes.append(f"{ing.user_term} plant part: {old.plant_part or '—'} → {ing.plant_part or '—'}")
        if old.botanical_name != ing.botanical_name:
            changes.append(
                f"{ing.user_term} identity: {old.botanical_name or old.identity_status.value} → "
                f"{ing.botanical_name or ing.identity_status.value}"
            )
    for iid, ing in a_ing.items():
        if iid not in b_ing:
            changes.append(f"Removed {ing.user_term}")
    for field in ("name", "dosage_form", "route", "intended_use", "target_market", "purpose", "entity_type"):
        old_v, new_v = getattr(a, field), getattr(b, field)
        if old_v != new_v:
            changes.append(f"{field.replace('_', ' ')}: {_plain(old_v) or '—'} → {_plain(new_v) or '—'}")
    if a.product_claims != b.product_claims:
        changes.append("Claims updated")
    if a.confirmed != b.confirmed:
        changes.append("Formulation confirmed" if b.confirmed else "Confirmation cleared")
    return changes


def _plain(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


_FIELD_ENUMS: dict[str, Any] = {
    "purpose": AbsPurpose,
    "entity_type": EntityType,
    "resource_source": ResourceSource,
    "legal_scope": LegalScope,
}


def _mutate(
    ctx: FormulationContext, action: Any, resolver: IngredientResolver | None
) -> tuple[str, str | None, list[str]]:
    t = action.type
    if t == "ADD_INGREDIENT":
        if ctx.find_ingredient(action.user_term) is not None:
            raise ActionRejected(f"{action.user_term} is already in the formulation.")
        ing = FormulationIngredient(
            id=new_id("ing"),
            user_term=action.user_term.strip(),
            quantity=action.quantity,
            unit=action.unit,
            plant_part=action.plant_part,
        )
        if resolver is not None:
            ing = resolver(ing)
        # A resolved identity may collide with an existing ingredient (e.g. "Giloy" vs "Guduchi").
        if ing.botanical_name and any(
            i.botanical_name == ing.botanical_name for i in ctx.ingredients
        ):
            raise ActionRejected(
                f"{action.user_term} resolves to {ing.botanical_name}, which is already in the formulation."
            )
        ctx.ingredients.append(ing)
        ctx.last_referenced_ingredient = ing.id
        return f"Added {ing.user_term} ({_fmt_qty(ing.quantity, ing.unit)})", ing.id, ["ingredients"]

    if t in {"REMOVE_INGREDIENT", "UPDATE_INGREDIENT", "RESOLVE_ENTITY"}:
        ing = next((i for i in ctx.ingredients if i.id == action.ingredient_id), None)
        if ing is None:
            raise ActionRejected("That ingredient is not in the current formulation.")
        if t == "REMOVE_INGREDIENT":
            ctx.ingredients = [i for i in ctx.ingredients if i.id != ing.id]
            if ctx.last_referenced_ingredient == ing.id:
                ctx.last_referenced_ingredient = None
            return f"Removed {ing.user_term}", ing.id, ["ingredients"]
        if t == "RESOLVE_ENTITY":
            try:
                resolve_by_user_choice(ing, action.botanical_name)
            except ValueError as exc:
                raise ActionRejected(str(exc)) from exc
            ctx.last_referenced_ingredient = ing.id
            return f"Resolved {ing.user_term} as {ing.botanical_name}", ing.id, ["identity"]
        before = _fmt_qty(ing.quantity, ing.unit)
        changed: list[str] = []
        if action.quantity is not None:
            ing.quantity = action.quantity
            changed.append("quantity")
        if action.unit is not None:
            ing.unit = action.unit
            changed.append("unit")
        if action.plant_part is not None:
            ing.plant_part = action.plant_part or None
            changed.append("plant_part")
        if action.user_term and action.user_term.strip() != ing.user_term:
            ing.user_term = action.user_term.strip()
            changed.append("user_term")
            if resolver is not None:
                resolver(ing)
        if not changed:
            raise ActionRejected("No change requested for that ingredient.")
        ctx.last_referenced_ingredient = ing.id
        if {"quantity", "unit"} & set(changed):
            summary = f"{ing.user_term}: {before} → {_fmt_qty(ing.quantity, ing.unit)}"
        else:
            summary = f"Updated {ing.user_term} ({', '.join(changed)})"
        return summary, ing.id, changed

    if t == "UPDATE_DOSAGE_FORM":
        old = ctx.dosage_form
        ctx.dosage_form = action.value.strip().lower()
        return f"Dosage form: {old or '—'} → {ctx.dosage_form}", None, ["dosage_form"]

    if t == "UPDATE_INTENDED_USE":
        old = ctx.intended_use
        ctx.intended_use = action.value.strip()
        return f"Intended use: {old or '—'} → {ctx.intended_use}", None, ["intended_use"]

    if t == "UPDATE_CLAIMS":
        ctx.product_claims = [c.strip() for c in action.claims if c and c.strip()]
        return f"Claims updated ({len(ctx.product_claims)})", None, ["product_claims"]

    if t == "UPDATE_FIELD":
        field = action.field
        raw = (action.value or "").strip() or None
        enum_cls = _FIELD_ENUMS.get(field)
        if enum_cls is not None and raw is not None:
            try:
                value: Any = enum_cls(raw.lower())
            except ValueError as exc:
                allowed = ", ".join(e.value for e in enum_cls)
                raise ActionRejected(f"Invalid {field}: {raw!r}. Allowed: {allowed}.") from exc
        else:
            value = raw
        if field == "legal_scope" and value is None:
            value = LegalScope.DOMESTIC
        if field == "jurisdiction" and value is None:
            value = "india"
        old = getattr(ctx, field)
        setattr(ctx, field, value)
        label = field.replace("_", " ")
        return f"{label.capitalize()}: {_plain(old) or '—'} → {_plain(value) or '—'}", None, [field]

    if t == "RESOLVE_BOTANICALS":
        if resolver is None:
            raise ActionRejected("Botanical resolver unavailable.")
        for ing in ctx.ingredients:
            if not ing.resolved_by_user:
                resolver(ing)
        resolved = sum(1 for i in ctx.ingredients if i.botanical_name)
        return f"Resolved {resolved}/{len(ctx.ingredients)} botanical identities", None, ["identity"]

    if t == "CONFIRM_FORMULATION":
        if not ctx.ingredients:
            raise ActionRejected("Add at least one ingredient before confirming.")
        ctx.confirmed = True
        return "Formulation confirmed", None, ["confirmed"]

    raise ActionRejected(f"Unsupported action {t}.")


_store: FormulationStore | None = None


def get_formulation_store() -> FormulationStore:
    global _store
    if _store is None:
        _store = FormulationStore()
    return _store


def source_type_of(value: str | None) -> FormulationSourceType:
    try:
        return FormulationSourceType(value or "manual")
    except ValueError:
        return FormulationSourceType.MANUAL
