"""Deterministic ABS fee arithmetic — the LLM never computes the fee."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from graph.models import AbsFeeCalculation, RetrievedSource

_PERCENT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:%|per\s*cent|percent)", re.IGNORECASE
)


def compute_abs_fee(turnover_inr: float, percentage: float) -> float:
    """fee = turnover * percentage / 100, rounded half-up to paise."""
    if turnover_inr < 0:
        raise ValueError("turnover must be non-negative")
    if not 0 <= percentage <= 100:
        raise ValueError("percentage must be between 0 and 100")
    fee = Decimal(str(turnover_inr)) * Decimal(str(percentage)) / Decimal(100)
    return float(fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def percentages_in_text(text: str) -> list[float]:
    return [float(m) for m in _PERCENT_RE.findall(text or "")]


def percentage_is_grounded(
    percentage: float, source_id: str | None, sources: list[RetrievedSource]
) -> bool:
    """True only if the cited source's text literally states this percentage."""
    if source_id is None:
        return False
    source = next((s for s in sources if s.id == source_id), None)
    if source is None:
        return False
    return any(abs(p - percentage) < 1e-9 for p in percentages_in_text(source.text))


def abs_calculation_node(state: dict[str, Any]) -> dict[str, Any]:
    turnover = state.get("annual_turnover_inr")
    override = state.get("percentage_override")
    selection = state.get("rate_selection")

    if turnover is None:
        return {}

    if override is not None:
        return {
            "calculation": AbsFeeCalculation(
                annual_turnover_inr=float(turnover),
                percentage=float(override),
                fee_inr=compute_abs_fee(float(turnover), float(override)),
                percentage_origin="user_override",
            )
        }

    if selection is None or selection.percentage is None:
        return {"escalation_reasons": ["missing_abs_rate_evidence"]}
    if not selection.grounded:
        return {"escalation_reasons": ["rate_not_grounded_in_source"]}

    return {
        "calculation": AbsFeeCalculation(
            annual_turnover_inr=float(turnover),
            percentage=selection.percentage,
            fee_inr=compute_abs_fee(float(turnover), selection.percentage),
            percentage_origin="source",
            source_id=selection.source_id,
        )
    }
