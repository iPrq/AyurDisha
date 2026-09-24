"""End-to-end Patent Advisor graph tests (scripted LLM, no paid API)."""

from __future__ import annotations

from graph.models import BotanicalStatus, LegalScope, VerificationOutcome
from graph.patent_advisor_graph import build_patent_advisor_graph
from retrieval.mock import MockLegalRetriever, get_fixture_corpus


def test_patent_advisor_domestic_ashwagandha(scripted_llm):
    graph = build_patent_advisor_graph(llm=scripted_llm)
    result = graph.invoke(
        {
            "product": "Ashwagandha capsule",
            "ingredients": ["Ashwagandha"],
            "language": "en",
            "jurisdiction": "india",
            "legal_scope": LegalScope.DOMESTIC,
        }
    )
    assert result["botanical_name"] == "Withania somnifera"
    assert result["botanical_status"] == BotanicalStatus.RESOLVED.value
    assert result["retrieved_sources"]
    assert result["section3"] is not None
    assert result["patentability_risk"] is not None
    assert result["patentability_risk_score"] >= 0.0
    assert result["prior_art"] is not None
    assert result["ip_routes"] is not None
    assert result["verification"] is not None
    assert result["final_answer"]


def test_patent_advisor_ambiguous_escalates(scripted_llm):
    graph = build_patent_advisor_graph(llm=scripted_llm)
    result = graph.invoke(
        {
            "product": "Ginseng tonic",
            "ingredients": ["ginseng"],
            "language": "en",
            "jurisdiction": "india",
            "legal_scope": "domestic",
        }
    )
    assert result["botanical_status"] == BotanicalStatus.AMBIGUOUS.value
    assert result["verification_status"] == VerificationOutcome.HUMAN_REVIEW_REQUIRED.value
    assert "ambiguous_botanical" in (result.get("escalation_reasons") or [])


def test_patent_advisor_international_uses_comparative_sources(scripted_llm):
    graph = build_patent_advisor_graph(llm=scripted_llm)
    result = graph.invoke(
        {
            "product": "Ashwagandha capsule",
            "ingredients": ["Ashwagandha"],
            "language": "en",
            "jurisdiction": "india",
            "legal_scope": LegalScope.INTERNATIONAL,
        }
    )
    sources = result.get("retrieved_sources") or []
    assert sources
    assert all(s.legal_scope == LegalScope.INTERNATIONAL for s in sources)


def test_patent_advisor_international_empty_corpus_human_review(scripted_llm):
    domestic_only = [
        s for s in get_fixture_corpus() if s.legal_scope == LegalScope.DOMESTIC
    ]
    graph = build_patent_advisor_graph(
        retriever=MockLegalRetriever(corpus=domestic_only),
        llm=scripted_llm,
    )
    result = graph.invoke(
        {
            "product": "Ashwagandha capsule",
            "ingredients": ["Ashwagandha"],
            "language": "en",
            "jurisdiction": "india",
            "legal_scope": LegalScope.INTERNATIONAL,
        }
    )
    assert result.get("retrieval_insufficient") is True
    assert result["verification_status"] == VerificationOutcome.HUMAN_REVIEW_REQUIRED.value
    assert "insufficient_international_evidence" in (
        result.get("escalation_reasons") or []
    )
