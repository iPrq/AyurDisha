"""Router helper: hydrate a tool's initial graph state from a stored formulation."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from graph.formulation.handoff import hydrate_state_from_formulation
from graph.formulation.store import FormulationNotFound, get_formulation_store
from graph.formulation.telemetry import log_event


def hydrate_from_formulation(initial: dict[str, Any], formulation_id: str, ingredients: list[str]) -> dict[str, Any]:
    try:
        ctx = get_formulation_store().get(formulation_id)
    except FormulationNotFound as exc:
        raise HTTPException(status_code=404, detail="Formulation not found (it may have expired).") from exc
    hydrate_state_from_formulation(initial, ctx, ingredients)
    log_event(
        "formulation_handoff",
        ingredient_count=len(ctx.ingredients),
        status="prefilled" if initial.get("botanicals_prefilled") else "renormalize",
    )
    return initial
