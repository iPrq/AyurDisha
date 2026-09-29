"""Clarification engine — asks only for missing information that materially affects a tool's output."""

from __future__ import annotations

from graph.formulation.models import (
    ClarificationOption,
    ClarificationRequest,
    FormulationContext,
    IdentityStatus,
    ReadinessResponse,
    ToolName,
)

PURPOSE_OPTIONS = [
    ClarificationOption(value="commercial_utilization", label="Commercial"),
    ClarificationOption(value="research", label="Research"),
    ClarificationOption(value="bio_survey", label="Bio-survey"),
    ClarificationOption(value="ipr", label="IPR / patent"),
]
ENTITY_OPTIONS = [
    ClarificationOption(value="indian", label="Indian entity"),
    ClarificationOption(value="foreign", label="Foreign entity"),
]


def _ambiguity_request(ctx: FormulationContext, tool: ToolName | None) -> ClarificationRequest | None:
    for ing in ctx.ingredients:
        if ing.identity_status == IdentityStatus.AMBIGUOUS and ing.candidates:
            return ClarificationRequest(
                kind="identity",
                field="botanical_identity",
                ingredient_id=ing.id,
                question=(
                    f"“{ing.user_term}” can refer to more than one plant. "
                    "Which botanical identity do you mean?"
                ),
                options=[
                    ClarificationOption(value=c.botanical_name, label=c.botanical_name)
                    for c in ing.candidates
                ],
                blocking_tool=tool,
            )
    return None


def missing_for_tool(ctx: FormulationContext, tool: ToolName) -> list[str]:
    missing: list[str] = []
    if not ctx.ingredients:
        missing.append("ingredients")
    if tool == "nba-abs":
        if ctx.purpose is None:
            missing.append("purpose")
        if ctx.entity_type is None:
            missing.append("entity_type")
    return missing


def clarification_for_tool(ctx: FormulationContext, tool: ToolName) -> ClarificationRequest | None:
    """First blocking question for ``tool`` — never asks for fields already in the context."""
    missing = missing_for_tool(ctx, tool)
    if "ingredients" in missing:
        return ClarificationRequest(
            kind="ingredients",
            field="ingredients",
            question="Which ingredients does the formulation contain?",
            blocking_tool=tool,
        )
    ambiguity = _ambiguity_request(ctx, tool)
    if ambiguity is not None:
        return ambiguity
    if "purpose" in missing:
        return ClarificationRequest(
            kind="field",
            field="purpose",
            question=(
                "I have the ingredients, but I still need the purpose of use to assess ABS "
                "applicability. Is it:"
            ),
            options=PURPOSE_OPTIONS,
            blocking_tool=tool,
        )
    if "entity_type" in missing:
        return ClarificationRequest(
            kind="field",
            field="entity_type",
            question="Is the applicant an Indian or a foreign entity? This changes which authority applies.",
            options=ENTITY_OPTIONS,
            blocking_tool=tool,
        )
    return None


def readiness(ctx: FormulationContext, tool: ToolName) -> ReadinessResponse:
    request = clarification_for_tool(ctx, tool)
    return ReadinessResponse(
        tool=tool,
        ready=request is None,
        clarification=request,
        missing=missing_for_tool(ctx, tool),
    )


def formulation_missing_information(ctx: FormulationContext) -> list[str]:
    """Fields worth surfacing in the extraction workspace (informational, not blocking)."""
    missing: list[str] = []
    if not ctx.ingredients:
        missing.append("ingredients")
    if any(i.quantity is None for i in ctx.ingredients):
        missing.append("quantities")
    if not ctx.dosage_form:
        missing.append("dosage_form")
    if not ctx.intended_use:
        missing.append("intended_use")
    if any(i.identity_status == IdentityStatus.AMBIGUOUS for i in ctx.ingredients):
        missing.append("ambiguous_identity")
    if any(i.identity_status == IdentityStatus.INSUFFICIENT_EVIDENCE for i in ctx.ingredients):
        missing.append("unresolved_identity")
    return missing
