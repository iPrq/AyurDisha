"""Deterministic ABS fee arithmetic and source-grounding checks."""

from __future__ import annotations

import pytest

from graph.models import AbsRateSelection, RetrievedSource
from graph.nba_abs.calculator import (
    abs_calculation_node,
    compute_abs_fee,
    percentage_is_grounded,
    percentages_in_text,
)

_RATES = RetrievedSource(
    id="rates",
    title="rates",
    text="up to Rs 1 crore: 0.1 per cent; up to Rs 3 crore: 0.2 per cent; above: 0.5%.",
)


def test_compute_abs_fee():
    assert compute_abs_fee(20_000_000, 0.2) == 40_000.0
    assert compute_abs_fee(0, 0.5) == 0.0
    # Decimal arithmetic avoids float drift (0.1 * 3 != 0.3 in binary floats).
    assert compute_abs_fee(333.33, 0.5) == 1.67


@pytest.mark.parametrize("turnover,pct", [(-1, 0.1), (100, -0.1), (100, 101)])
def test_compute_abs_fee_rejects_invalid(turnover, pct):
    with pytest.raises(ValueError):
        compute_abs_fee(turnover, pct)


def test_percentages_in_text():
    assert percentages_in_text(_RATES.text) == [0.1, 0.2, 0.5]


def test_percentage_grounding():
    assert percentage_is_grounded(0.2, "rates", [_RATES])
    assert not percentage_is_grounded(0.3, "rates", [_RATES])
    assert not percentage_is_grounded(0.2, "other", [_RATES])
    assert not percentage_is_grounded(0.2, None, [_RATES])


def test_calculation_node_uses_grounded_rate():
    sel = AbsRateSelection(percentage=0.2, source_id="rates", grounded=True)
    out = abs_calculation_node({"annual_turnover_inr": 20_000_000, "rate_selection": sel})
    calc = out["calculation"]
    assert calc.fee_inr == 40_000.0
    assert calc.percentage_origin == "source"
    assert calc.source_id == "rates"


def test_calculation_node_refuses_ungrounded_rate():
    sel = AbsRateSelection(percentage=0.3, source_id="rates", grounded=False)
    out = abs_calculation_node({"annual_turnover_inr": 20_000_000, "rate_selection": sel})
    assert "calculation" not in out
    assert out["escalation_reasons"] == ["rate_not_grounded_in_source"]


def test_calculation_node_override_and_missing_turnover():
    out = abs_calculation_node({"annual_turnover_inr": 1_000_000, "percentage_override": 1.0})
    assert out["calculation"].fee_inr == 10_000.0
    assert out["calculation"].percentage_origin == "user_override"
    assert abs_calculation_node({}) == {}
