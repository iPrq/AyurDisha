"""Lightweight scenario mode — a temporary context, never a legal determination."""

from __future__ import annotations

from pydantic import BaseModel, Field

from graph.formulation.characterize import characterize
from graph.formulation.models import FormulationContext, ScenarioChange
from graph.formulation.store import diff_contexts

SCENARIO_BANNER = "SCENARIO ANALYSIS — NOT A DETERMINATION"


class ScenarioResult(BaseModel):
    banner: str = SCENARIO_BANNER
    base_version: int
    scenario_context: FormulationContext
    changes: list[str] = Field(default_factory=list)
    potentially_affected: list[str] = Field(default_factory=list)
    note: str = (
        "This scenario was not applied to your formulation. Areas listed may need re-analysis; "
        "no legal or regulatory outcome is implied."
    )


def build_scenario(ctx: FormulationContext, changes: list[ScenarioChange]) -> ScenarioResult:
    scenario = ctx.model_copy(deep=True)
    for change in changes:
        ing = next((i for i in scenario.ingredients if i.id == change.ingredient_id), None)
        if ing is None:
            raise ValueError("Scenario references an ingredient that is not in the formulation.")
        if change.quantity is not None:
            ing.quantity = change.quantity
        if change.unit is not None:
            ing.unit = change.unit
    scenario.formulation_characteristics = characterize(scenario)
    affected: list[str] = []
    if any(c.quantity is not None or c.unit is not None for c in changes):
        affected = ["Composition", "Patent analysis", "Regulatory context", "ABS context"]
    return ScenarioResult(
        base_version=ctx.version,
        scenario_context=scenario,
        changes=diff_contexts(ctx, scenario),
        potentially_affected=affected,
    )
