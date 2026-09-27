"""Risk model with 15 clauses, verifier evidence-gap escalation, end-to-end graph."""

from __future__ import annotations

import pytest

from config import Settings
from graph.models import (
    LegalScope,
    RetrievedSource,
    Section3Clause,
    Section3ProvisionResult,
    Section3Results,
    VerificationOutcome,
)
from graph.patent_advisor.risk import calculate_patentability_risk
from graph.patent_advisor_graph import build_patent_advisor_graph
from graph.shared.verifier import critic_verifier_node, verify_claims
from tests.conftest import ScriptedLLM

WEIGHTS = Settings(section3_weight_d=0.35, section3_weight_e=0.30, section3_weight_p=0.35)


def _risk(*triggered: str, untriggered: tuple[str, ...] = ()):
    provisions = [Section3ProvisionResult(clause=c, triggered=True) for c in triggered]
    provisions += [Section3ProvisionResult(clause=c, triggered=False) for c in untriggered]
    return calculate_patentability_risk(Section3Results(provisions=provisions), settings=WEIGHTS)


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "triggered, expected",
    [((), 0.0), (("3(e)",), 0.30), (("3(d)", "3(p)"), 0.70), (("3(d)", "3(e)", "3(p)"), 1.0)],
)
def test_existing_dep_results_unchanged(triggered, expected):
    risk = _risk(*triggered)
    assert risk.score == pytest.approx(expected)
    assert risk.unweighted_triggered_clauses == []


def test_new_clauses_get_no_invented_weight():
    new = [c for c in Section3Clause if c not in {Section3Clause.D, Section3Clause.E, Section3Clause.P}]
    risk = _risk(*[c.value for c in new])
    assert risk.score == 0.0
    assert risk.unweighted_triggered_clauses == new
    assert risk.triggered_clauses == new


def test_3d_plus_3k_is_deterministic():
    first = _risk("3(d)", "3(k)")
    second = _risk("3(k)", "3(d)")
    for risk in (first, second):
        assert risk.score == pytest.approx(0.35)
        assert risk.unweighted_triggered_clauses == [Section3Clause.K]
        assert set(risk.triggered_clauses) == {Section3Clause.D, Section3Clause.K}


def test_duplicate_clause_counted_once():
    risk = _risk("3(d)", "3(d)")
    assert risk.score == pytest.approx(0.35)
    assert risk.triggered_clauses == [Section3Clause.D]


def test_duplicate_where_one_copy_untriggered():
    risk = _risk("3(d)", untriggered=("3(d)",))
    assert risk.score == pytest.approx(0.35)


def test_risk_indicator_semantics_unchanged():
    risk = _risk("3(k)")
    assert risk.label == "decision_support_risk_indicator"
    assert "not a probability" in risk.disclaimer


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------


def _src(sid: str, section: str | None) -> RetrievedSource:
    return RetrievedSource(
        id=sid,
        title="fixture",
        text="[TEST FIXTURE — placeholder]",
        section=section,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    )


def test_evidence_gap_forces_human_review(scripted_llm):
    # scripted verifier would otherwise PASS
    result = verify_claims(
        ["claim"],
        [_src("fixture-in-s3d", "3(d)")],
        escalation_reasons=["section3_evidence_gap"],
        llm=scripted_llm,
    )
    assert result.outcome == VerificationOutcome.HUMAN_REVIEW_REQUIRED
    assert "section3_evidence_gap" in result.escalation_reasons


def test_without_evidence_gap_scripted_verifier_passes(scripted_llm):
    result = verify_claims(["claim"], [_src("fixture-in-s3d", "3(d)")], llm=scripted_llm)
    assert result.outcome == VerificationOutcome.PASS


def test_verifier_node_carries_evidence_gap(scripted_llm):
    state = {
        "product": "x",
        "ingredients": [],
        "language": "en",
        "jurisdiction": "india",
        "legal_scope": "domestic",
        "retrieved_sources": [_src("fixture-in-s3d", "3(d)")],
        "escalation_reasons": ["section3_evidence_gap"],
        "final_answer": "Draft.",
    }
    update = critic_verifier_node(state, llm=scripted_llm)  # type: ignore[arg-type]
    assert update["verification_status"] == VerificationOutcome.HUMAN_REVIEW_REQUIRED.value


# ---------------------------------------------------------------------------
# End-to-end graph
# ---------------------------------------------------------------------------


class GapLLM(ScriptedLLM):
    """3(d) with valid evidence, 3(j) with a fabricated source id, plus an unsupported 3(g)."""

    def __call__(self, schema, system, user):
        if schema.__name__ == "Section3Results":
            return {
                "provisions": [
                    {"clause": "3(d)", "triggered": True, "reason": "d", "evidence_source_ids": ["fixture-in-s3d"]},
                    {"clause": "Section 3(j)", "triggered": True, "reason": "j", "evidence_source_ids": ["fabricated-id"]},
                    {"clause": "3(g)", "triggered": True, "reason": "g", "evidence_source_ids": ["fixture-in-s3d"]},
                ],
                "summary": "Scripted Section 3 output with a fabricated source id.",
            }
        return super().__call__(schema, system, user)


def _run(llm):
    graph = build_patent_advisor_graph(llm=llm, settings=Settings())
    return graph.invoke(
        {
            "product": "Ashwagandha capsule",
            "ingredients": ["Ashwagandha"],
            "language": "en",
            "jurisdiction": "india",
            "legal_scope": LegalScope.DOMESTIC,
        }
    )


def test_e2e_fake_source_id_requires_human_review_without_corrupting_risk():
    result = _run(GapLLM())
    s3 = result["section3"]
    by_clause = {p.clause: p for p in s3.provisions}
    assert by_clause[Section3Clause.D].triggered is True
    j = by_clause[Section3Clause.J]
    assert j.triggered is False and j.evidence_gap is True and j.evidence_source_ids == []
    assert s3.evidence_gap_clauses == [Section3Clause.J]
    assert s3.rejected_clauses == ["3(g)"]

    assert result["patentability_risk_score"] == pytest.approx(0.35)
    assert result["patentability_risk"].triggered_clauses == [Section3Clause.D]

    reasons = result["escalation_reasons"]
    assert "section3_evidence_gap" in reasons
    assert "unsupported_section3_clause" in reasons
    assert result["verification_status"] == VerificationOutcome.HUMAN_REVIEW_REQUIRED.value
    assert result["final_answer"]


def test_e2e_existing_scripted_flow_still_passes(scripted_llm):
    result = _run(scripted_llm)
    assert result["patentability_risk_score"] == pytest.approx(1.0)
    assert result["section3"].evidence_gap_clauses == []
    assert "section3_evidence_gap" not in (result.get("escalation_reasons") or [])
