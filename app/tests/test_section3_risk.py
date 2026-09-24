"""Tests for deterministic Section 3 risk indicator + LLM scorer (scripted)."""

from __future__ import annotations

from config import Settings
from graph.models import (
    LegalScope,
    Section3Clause,
    Section3ProvisionResult,
    Section3Results,
)
from graph.patent_advisor.risk import calculate_patentability_risk
from graph.patent_advisor.section3 import score_section3
from retrieval.mock import get_mock_retriever


def test_risk_sums_triggered_weights():
    settings = Settings(
        section3_weight_d=0.35,
        section3_weight_e=0.30,
        section3_weight_p=0.35,
    )
    section3 = Section3Results(
        provisions=[
            Section3ProvisionResult(clause=Section3Clause.D, triggered=True),
            Section3ProvisionResult(clause=Section3Clause.E, triggered=False),
            Section3ProvisionResult(clause=Section3Clause.P, triggered=True),
        ]
    )
    risk = calculate_patentability_risk(section3, settings=settings)
    assert abs(risk.score - 0.70) < 1e-9
    assert Section3Clause.D in risk.triggered_clauses
    assert Section3Clause.P in risk.triggered_clauses
    assert risk.label == "decision_support_risk_indicator"


def test_risk_zero_when_none_triggered():
    section3 = Section3Results(
        provisions=[
            Section3ProvisionResult(clause=Section3Clause.D, triggered=False),
            Section3ProvisionResult(clause=Section3Clause.E, triggered=False),
            Section3ProvisionResult(clause=Section3Clause.P, triggered=False),
        ]
    )
    risk = calculate_patentability_risk(section3)
    assert risk.score == 0.0
    assert risk.triggered_clauses == []


def test_score_section3_domestic_from_fixtures(scripted_llm):
    sources = get_mock_retriever().retrieve(
        "Section 3 traditional knowledge",
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
    )
    result = score_section3(
        sources,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        llm=scripted_llm,
    )
    assert not result.insufficient_evidence
    triggered = [p for p in result.provisions if p.triggered]
    assert triggered
    assert any(p.clause == Section3Clause.P for p in triggered)


def test_score_section3_international_without_inventing(scripted_llm):
    sources = get_mock_retriever().retrieve(
        "comparative",
        jurisdiction="india",
        legal_scope=LegalScope.INTERNATIONAL,
    )
    result = score_section3(
        sources,
        jurisdiction="india",
        legal_scope=LegalScope.INTERNATIONAL,
        llm=scripted_llm,
    )
    assert all(not p.triggered for p in result.provisions)


def test_score_section3_empty_sources_no_llm_call():
    result = score_section3(
        [], jurisdiction="india", legal_scope=LegalScope.DOMESTIC, llm=None
    )
    assert result.insufficient_evidence
    assert result.provisions == []
