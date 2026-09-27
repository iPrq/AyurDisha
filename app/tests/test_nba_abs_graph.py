"""End-to-end NBA / ABS graph tests (scripted LLM, mock corpus, no paid API)."""

from __future__ import annotations

from graph.models import (
    AbsApplicability,
    AbsApplicabilityStatus,
    AbsRateSelection,
    ReviewFinding,
    VerificationOutcome,
)
from graph.nba_abs_graph import build_nba_abs_graph
from retrieval.mock import MockLegalRetriever
from tests.conftest import ScriptedLLM

_REQUEST = {
    "product": "Ashwagandha capsule",
    "ingredients": ["Ashwagandha"],
    "language": "en",
    "jurisdiction": "india",
    "purpose": "commercial_utilization",
    "entity_type": "indian",
    "resource_source": "wild",
    "annual_turnover_inr": 20_000_000,
}


def test_abs_grounded_rate_deterministic_fee(scripted_llm):
    result = build_nba_abs_graph(llm=scripted_llm).invoke(dict(_REQUEST))
    assert result["applicability"].status == AbsApplicabilityStatus.APPLICABLE
    assert result["rate_selection"].grounded is True
    calc = result["calculation"]
    assert calc.fee_inr == 40_000.0
    assert calc.percentage == 0.2
    assert calc.source_id == "fixture-in-abs-rates"
    assert "fixture-in-abs-rates" in {s.id for s in result["retrieved_sources"]}
    assert "[CALCULATION]" in result["final_answer"]
    assert result["verification_status"] == VerificationOutcome.PASS.value


def test_abs_ungrounded_rate_blocks_calculation():
    llm = ScriptedLLM(
        overrides={
            "AbsRateSelection": AbsRateSelection(
                percentage=0.3, source_id="fixture-in-abs-rates", rationale="guess"
            )
        }
    )
    result = build_nba_abs_graph(llm=llm).invoke(dict(_REQUEST))
    assert result["rate_selection"].grounded is False
    assert "calculation" not in result
    assert "rate_not_grounded_in_source" in result["escalation_reasons"]
    assert result["verification_status"] == VerificationOutcome.HUMAN_REVIEW_REQUIRED.value


def test_abs_not_applicable_skips_rate_and_calculation():
    llm = ScriptedLLM(
        overrides={
            "AbsApplicability": AbsApplicability(
                status=AbsApplicabilityStatus.NOT_APPLICABLE,
                summary="Cultivated medicinal plant exemption applies.",
                exemptions_considered=[
                    ReviewFinding(
                        summary="Cultivated medicinal plants exempted.",
                        evidence_source_ids=["fixture-in-abs-bd-act"],
                    )
                ],
            )
        }
    )
    result = build_nba_abs_graph(llm=llm).invoke({**_REQUEST, "resource_source": "cultivated"})
    assert result["applicability"].status == AbsApplicabilityStatus.NOT_APPLICABLE
    assert "rate_selection" not in result
    assert "calculation" not in result
    assert "AbsRateSelection" not in llm.calls


def test_abs_percentage_override_is_labeled(scripted_llm):
    result = build_nba_abs_graph(llm=scripted_llm).invoke(
        {**_REQUEST, "percentage_override": 1.0}
    )
    calc = result["calculation"]
    assert calc.percentage_origin == "user_override"
    assert calc.fee_inr == 200_000.0
    assert "AbsRateSelection" not in scripted_llm.calls


def test_abs_empty_corpus_escalates(scripted_llm):
    result = build_nba_abs_graph(
        llm=scripted_llm, retriever=MockLegalRetriever(corpus=[])
    ).invoke(dict(_REQUEST))
    assert result["applicability"].status == AbsApplicabilityStatus.UNCERTAIN
    assert "calculation" not in result
    assert result["verification_status"] == VerificationOutcome.HUMAN_REVIEW_REQUIRED.value


def test_abs_without_turnover_computes_nothing(scripted_llm):
    request = {k: v for k, v in _REQUEST.items() if k != "annual_turnover_inr"}
    result = build_nba_abs_graph(llm=scripted_llm).invoke(request)
    assert "calculation" not in result
    assert "annual turnover not provided" in result["final_answer"]
