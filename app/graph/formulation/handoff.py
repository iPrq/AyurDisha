"""Cross-tool context transfer: FormulationContext → existing tool requests (no duplicated logic)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from graph.formulation.clarify import missing_for_tool
from graph.formulation.identity import botanical_results_for_handoff
from graph.formulation.models import FormulationContext, FormulationSourceType, IdentityStatus, ToolName

TOOL_ROUTES: dict[str, str] = {"review": "/review", "patent": "/patent", "nba-abs": "/nba-abs"}


class ToolHandoff(BaseModel):
    tool: ToolName
    route: str
    formulation_id: str
    version: int
    fields: dict[str, Any] = Field(default_factory=dict, description="Form fields to autofill, in display order")
    derived_fields: list[str] = Field(default_factory=list, description="Fields composed rather than user-stated")
    missing: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


def display_name(ctx: FormulationContext) -> tuple[str, bool]:
    """Product name, and whether it was composed from ingredients (not user-stated)."""
    if ctx.name and ctx.name.strip():
        return ctx.name.strip(), False
    terms = [i.user_term for i in ctx.ingredients[:3]]
    base = " + ".join(terms) if terms else "Untitled formulation"
    if ctx.dosage_form:
        base = f"{base} {ctx.dosage_form}"
    return base, True


def formulation_notes(ctx: FormulationContext) -> str:
    """User-provided formulation summary passed to downstream prompts as context (never evidence)."""
    lines = ["Formulation (from AyurDisha Formulation Intelligence; user-provided, not evidence):"]
    for ing in ctx.ingredients:
        qty = f" {ing.quantity:g} {ing.unit or ''}".rstrip() if ing.quantity is not None else ""
        ident = ing.botanical_name or f"identity {ing.identity_status.value}"
        part = f", part: {ing.plant_part}" if ing.plant_part else ""
        lines.append(f"- {ing.user_term}{qty} ({ident}{part})")
    for label, value in (
        ("Dosage form", ctx.dosage_form),
        ("Route", ctx.route),
        ("Intended use", ctx.intended_use),
        ("Target market", ctx.target_market),
    ):
        if value:
            lines.append(f"{label}: {value}")
    if ctx.product_claims:
        lines.append("Stated claims: " + "; ".join(ctx.product_claims))
    for c in ctx.formulation_characteristics:
        if c.origin == "derived":
            lines.append(f"{c.label}: {c.value}")
    return "\n".join(lines)


def build_handoff(ctx: FormulationContext, tool: ToolName) -> ToolHandoff:
    name, derived = display_name(ctx)
    ingredients = [i.user_term for i in ctx.ingredients]
    fields: dict[str, Any] = {"product": name, "ingredients": ingredients}
    if tool == "review":
        if ctx.dosage_form:
            fields["dosage_form"] = ctx.dosage_form
        if ctx.intended_use:
            fields["intended_use"] = ctx.intended_use
        fields["target_market"] = ctx.target_market or ""
        fields["legal_scope"] = ctx.legal_scope.value
    elif tool == "patent":
        fields["legal_scope"] = ctx.legal_scope.value
        if ctx.product_claims:
            fields["claims"] = ctx.product_claims
    else:
        fields["purpose"] = ctx.purpose.value if ctx.purpose else None
        fields["entity_type"] = ctx.entity_type.value if ctx.entity_type else None
        fields["resource_source"] = ctx.resource_source.value if ctx.resource_source else "unknown"
    return ToolHandoff(
        tool=tool,
        route=TOOL_ROUTES[tool],
        formulation_id=ctx.formulation_id,
        version=ctx.version,
        fields=fields,
        derived_fields=["product"] if derived else [],
        missing=missing_for_tool(ctx, tool),
        summary={
            "name": name,
            "ingredient_count": len(ctx.ingredients),
            "dosage_form": ctx.dosage_form,
            "normalized_botanicals": [i.botanical_name for i in ctx.ingredients if i.botanical_name],
            "biological_resources": ctx.biological_resources,
            "ambiguous": [i.user_term for i in ctx.ingredients if i.identity_status == IdentityStatus.AMBIGUOUS],
        },
    )


def hydrate_state_from_formulation(
    initial: dict[str, Any], ctx: FormulationContext, request_ingredients: list[str]
) -> dict[str, Any]:
    """Add formulation context to a tool's initial graph state.

    Pre-resolved botanicals are reused only when the request's ingredient list still matches the
    formulation (the user may have edited the form after import); otherwise normal normalization runs.
    """
    initial["formulation_id"] = ctx.formulation_id
    by_term = {i.user_term.strip().lower(): i for i in ctx.ingredients}
    wanted = [t.strip().lower() for t in request_ingredients if t and t.strip()]
    if wanted and all(t in by_term for t in wanted):
        ordered = [by_term[t] for t in dict.fromkeys(wanted)]
        results = botanical_results_for_handoff(ordered)
        initial["botanicals"] = results
        initial["botanical"] = results[0]
        initial["botanical_input"] = results[0].input_term
        initial["botanicals_prefilled"] = True
        synonyms: list[str] = []
        for ing in ordered:
            if ing.botanical_name:
                synonyms.extend(s for s in ing.synonyms if s.lower() != ing.botanical_name.lower())
        initial["retrieval_synonyms"] = list(dict.fromkeys(synonyms))[:8]
    notes = formulation_notes(ctx)
    existing = (initial.get("document_text") or "").strip()
    if ctx.source_type == FormulationSourceType.PATENT_PDF and ctx.raw_text and not existing:
        existing = ctx.raw_text
    initial["document_text"] = f"{notes}\n\n{existing}".strip() if existing else notes
    return initial
