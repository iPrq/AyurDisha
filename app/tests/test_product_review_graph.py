"""End-to-end Product Review graph tests (scripted LLM + mock web search, no paid API)."""

from __future__ import annotations

from graph.models import (
    BotanicalStatus,
    DimensionRating,
    LegalScope,
    VerificationOutcome,
)
from graph.product_review_graph import build_product_review_graph
from retrieval.mock import MockLegalRetriever, get_fixture_corpus
from websearch.base import NullWebSearcher, WebSearchError
from websearch.mock import MockWebSearcher

_REQUEST = {
    "product": "Ashwagandha capsule",
    "ingredients": ["Ashwagandha", "Turmeric"],
    "language": "en",
    "jurisdiction": "india",
    "legal_scope": "domestic",
}


def test_product_review_domestic(scripted_llm):
    searcher = MockWebSearcher()
    graph = build_product_review_graph(llm=scripted_llm, searcher=searcher)
    result = graph.invoke(dict(_REQUEST))

    names = [b.botanical_name for b in result["botanicals"]]
    assert names == ["Withania somnifera", "Curcuma longa"]

    market = result["market_feasibility"]
    legal = result["legal_compliance"]
    resource = result["resource_accessibility"]
    assert market.rating == DimensionRating.MODERATE
    assert [c.name for c in market.competitors] == ["Listed competitor"]
    assert legal.rating == DimensionRating.MODERATE
    assert resource.rating == DimensionRating.FAVORABLE

    legal_ids = {s.id for s in result["legal_sources"]}
    assert "fixture-in-reg-dca-asu" in legal_ids
    assert all(
        s.source_type in {"regulation_fixture", "web_fixture"} for s in result["legal_sources"]
    )

    source_ids = {s.id for s in result["retrieved_sources"]}
    assert legal_ids | {s.id for s in result["market_sources"]} <= source_ids
    assert "no combined score" in result["combined_summary"]
    assert result["verification_status"] == VerificationOutcome.PASS.value
    assert any("Withania somnifera" in q for q in searcher.queries)


def test_product_review_ambiguous_botanical_escalates(scripted_llm):
    graph = build_product_review_graph(llm=scripted_llm, searcher=MockWebSearcher())
    result = graph.invoke({**_REQUEST, "ingredients": ["ginseng"]})
    assert result["botanicals"][0].status == BotanicalStatus.AMBIGUOUS
    assert "ambiguous_botanical" in result["escalation_reasons"]
    assert result["verification_status"] == VerificationOutcome.HUMAN_REVIEW_REQUIRED.value


def test_product_review_no_web_evidence_marks_dimensions_insufficient(scripted_llm):
    graph = build_product_review_graph(llm=scripted_llm, searcher=NullWebSearcher())
    result = graph.invoke(dict(_REQUEST))
    assert result["market_feasibility"].rating == DimensionRating.INSUFFICIENT_EVIDENCE
    assert result["resource_accessibility"].rating == DimensionRating.INSUFFICIENT_EVIDENCE
    # Legal still has corpus evidence.
    assert result["legal_compliance"].rating == DimensionRating.MODERATE
    reasons = result["escalation_reasons"]
    assert {"missing_market_evidence", "missing_resource_evidence"} <= set(reasons)
    assert result["verification_status"] == VerificationOutcome.HUMAN_REVIEW_REQUIRED.value


def test_product_review_web_search_failure_escalates(scripted_llm):
    class Broken:
        def search(self, query, *, num_results=5, include_domains=None):
            raise WebSearchError("503")

    graph = build_product_review_graph(llm=scripted_llm, searcher=Broken())
    result = graph.invoke(dict(_REQUEST))
    assert "web_search_failed" in result["escalation_reasons"]
    assert result["verification_status"] == VerificationOutcome.HUMAN_REVIEW_REQUIRED.value


def test_product_review_international_without_corpus_never_invents_law(scripted_llm):
    domestic_only = [s for s in get_fixture_corpus() if s.legal_scope == LegalScope.DOMESTIC]
    graph = build_product_review_graph(
        llm=scripted_llm,
        retriever=MockLegalRetriever(corpus=domestic_only),
        searcher=NullWebSearcher(),
    )
    result = graph.invoke({**_REQUEST, "legal_scope": "international", "target_market": "EU"})
    legal = result["legal_compliance"]
    assert legal.insufficient_evidence
    assert legal.rating == DimensionRating.INSUFFICIENT_EVIDENCE
    assert "insufficient_international_evidence" in result["escalation_reasons"]
    assert result["verification_status"] == VerificationOutcome.HUMAN_REVIEW_REQUIRED.value


def test_product_review_international_uses_comparative_regulation(scripted_llm):
    graph = build_product_review_graph(llm=scripted_llm, searcher=NullWebSearcher())
    result = graph.invoke({**_REQUEST, "legal_scope": "international"})
    assert {s.id for s in result["legal_sources"]} == {"fixture-intl-reg-thmp"}
    assert result["legal_compliance"].legal_scope == LegalScope.INTERNATIONAL
