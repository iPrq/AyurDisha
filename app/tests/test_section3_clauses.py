"""Section 3 clause representation: 15 supported clauses, no 3(g), normalization, safe rejection."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from graph.models import (
    SUPPORTED_SECTION3_CLAUSES,
    UNSUPPORTED_SECTION3_CLAUSES,
    Section3Clause,
    Section3ProvisionResult,
    Section3Results,
)

EXPECTED = [f"3({c})" for c in "abcdefhijklmnop"]


def test_exactly_fifteen_supported_clauses():
    assert list(SUPPORTED_SECTION3_CLAUSES) == EXPECTED
    assert len(Section3Clause) == 15
    assert [c.value for c in Section3Clause] == EXPECTED


def test_3g_is_not_supported():
    assert "3(g)" not in SUPPORTED_SECTION3_CLAUSES
    assert "3(g)" in UNSUPPORTED_SECTION3_CLAUSES
    assert not hasattr(Section3Clause, "G")
    with pytest.raises(ValueError):
        Section3Clause("3(g)")
    with pytest.raises(ValidationError):
        Section3ProvisionResult(clause="3(g)")


@pytest.mark.parametrize("raw", ["3(k)", "3 (k)", "Section 3(k)", "3(K)", "section 3 ( k )"])
def test_clause_normalization(raw):
    assert Section3ProvisionResult(clause=raw).clause == Section3Clause.K


def test_existing_dep_clauses_unchanged():
    assert Section3Clause.D.value == "3(d)"
    assert Section3Clause.E.value == "3(e)"
    assert Section3Clause.P.value == "3(p)"


def test_unsupported_clauses_rejected_and_recorded():
    result = Section3Results.model_validate(
        {
            "provisions": [
                {"clause": "3(d)", "triggered": True, "evidence_source_ids": ["x"]},
                {"clause": "3(g)", "triggered": True},
                {"clause": "Section 3(q)", "triggered": False},
                {"clause": "3 (k)", "triggered": False},
            ],
            "summary": "s",
        }
    )
    assert [p.clause for p in result.provisions] == [Section3Clause.D, Section3Clause.K]
    assert result.rejected_clauses == ["3(g)", "3(q)"]


def test_new_fields_default_to_empty():
    result = Section3Results()
    assert result.rejected_clauses == []
    assert result.evidence_gap_clauses == []
    assert Section3ProvisionResult(clause="3(d)").evidence_gap is False


# ---------------------------------------------------------------------------
# Section 3 evidence validation (scripted LLM, placeholder sources)
# ---------------------------------------------------------------------------

from graph.models import LegalScope, RetrievedSource  # noqa: E402
from graph.patent_advisor.section3 import score_section3, section3_scorer_node  # noqa: E402


def _src(sid: str, section: str | None, source_type: str = "statute") -> RetrievedSource:
    return RetrievedSource(
        id=sid,
        title=f"[TEST FIXTURE] {sid}",
        text="[TEST FIXTURE — placeholder, not statutory text]",
        section=section,
        source_type=source_type,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    )


SOURCES = [
    _src("s3k", "3(k)"),
    _src("s3d", "3(d)"),
    _src("guide", None, "guideline"),
    _src("preamble", "3"),
]


def _llm(provisions, **extra):
    def _call(schema, system, user):
        assert schema.__name__ == "Section3Results"
        return {"provisions": provisions, "summary": "scripted", **extra}

    return _call


def _k(ids, triggered=True):
    return [{"clause": "3(k)", "triggered": triggered, "reason": "r", "evidence_source_ids": ids}]


def test_valid_3k_evidence_accepted():
    r = score_section3(SOURCES, llm=_llm(_k(["s3k"])))
    p = r.provisions[0]
    assert p.triggered and p.evidence_source_ids == ["s3k"] and not p.evidence_gap
    assert r.evidence_gap_clauses == []


def test_fake_evidence_id_rejected_and_gap_recorded():
    r = score_section3(SOURCES, llm=_llm(_k(["made-up-id"])))
    p = r.provisions[0]
    assert p.triggered is False
    assert p.evidence_source_ids == []
    assert p.evidence_gap is True
    assert "trigger cleared" in p.reason
    assert r.evidence_gap_clauses == [Section3Clause.K]


def test_3k_citing_only_3d_labelled_source_rejected():
    r = score_section3(SOURCES, llm=_llm(_k(["s3d"])))
    p = r.provisions[0]
    assert not p.triggered and p.evidence_gap and p.evidence_source_ids == []


def test_3k_citing_unlabelled_guideline_accepted():
    r = score_section3(SOURCES, llm=_llm(_k(["guide"])))
    assert r.provisions[0].triggered and r.provisions[0].evidence_source_ids == ["guide"]


def test_preamble_counts_as_unlabelled_support():
    r = score_section3(SOURCES, llm=_llm(_k(["preamble"])))
    assert r.provisions[0].triggered


def test_mixed_ids_keep_only_valid_clause_evidence():
    r = score_section3(SOURCES, llm=_llm(_k(["s3d", "fake", "s3k"])))
    assert r.provisions[0].triggered and r.provisions[0].evidence_source_ids == ["s3k"]


def test_untriggered_provision_is_not_an_evidence_gap():
    r = score_section3(SOURCES, llm=_llm(_k(["fake"], triggered=False)))
    assert r.provisions[0].evidence_gap is False
    assert r.evidence_gap_clauses == []


def test_llm_cannot_self_report_evidence_gap_fields():
    r = score_section3(
        SOURCES,
        llm=_llm(
            [{"clause": "3(k)", "triggered": True, "evidence_source_ids": ["s3k"], "evidence_gap": True}],
            evidence_gap_clauses=["3(d)"],
        ),
    )
    assert r.provisions[0].evidence_gap is False
    assert r.evidence_gap_clauses == []


def test_existing_3d_behaviour_preserved():
    r = score_section3(
        SOURCES,
        llm=_llm([{"clause": "3(d)", "triggered": True, "evidence_source_ids": ["s3d"]}]),
    )
    assert r.provisions[0].triggered and r.provisions[0].evidence_source_ids == ["s3d"]


def _node(llm):
    state = {
        "retrieved_sources": SOURCES,
        "jurisdiction": "india",
        "legal_scope": "domestic",
    }
    return section3_scorer_node(state, llm=llm)  # type: ignore[arg-type]


def test_node_escalates_evidence_gap():
    update = _node(_llm(_k(["made-up-id"])))
    assert "section3_evidence_gap" in update["escalation_reasons"]
    assert update["patentability_risk_score"] == 0.0


def test_node_unsupported_clause_does_not_crash_and_is_recorded():
    update = _node(
        _llm(
            [
                {"clause": "3(g)", "triggered": True, "evidence_source_ids": ["s3k"]},
                {"clause": "3(q)", "triggered": True},
                {"clause": "3(k)", "triggered": True, "evidence_source_ids": ["s3k"]},
            ]
        )
    )
    s3 = update["section3"]
    assert s3.rejected_clauses == ["3(g)", "3(q)"]
    assert [p.clause for p in s3.provisions] == [Section3Clause.K]
    assert "unsupported_section3_clause" in update["escalation_reasons"]
    assert "section3_evidence_gap" not in update["escalation_reasons"]


def test_node_clean_result_adds_no_escalation():
    update = _node(_llm(_k(["s3k"])))
    assert "escalation_reasons" not in update


def test_prompts_name_all_supported_clauses_and_exclude_3g():
    from graph.prompts import SECTION3_SYSTEM

    captured = {}

    def _capture(schema, system, user):
        captured["system"], captured["user"] = system, user
        return {"provisions": [], "summary": "s"}

    score_section3(SOURCES, llm=_capture)
    for ref in SUPPORTED_SECTION3_CLAUSES:
        assert ref in SECTION3_SYSTEM and ref in captured["user"]
    assert "Never analyze or return 3(g)" in SECTION3_SYSTEM
    assert "Never return 3(g)" in captured["user"]
