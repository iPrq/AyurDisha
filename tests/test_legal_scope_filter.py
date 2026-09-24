"""Tests for jurisdiction / legal_scope retrieval filters (no paid API)."""

from __future__ import annotations

from graph.models import LegalScope
from retrieval.base import filter_sources, matches_scope_filters
from retrieval.mock import get_fixture_corpus, get_mock_retriever


def test_domestic_filter_india_only():
    corpus = get_fixture_corpus()
    hits = filter_sources(
        corpus, jurisdiction="india", legal_scope=LegalScope.DOMESTIC
    )
    assert hits
    assert all(s.legal_scope == LegalScope.DOMESTIC for s in hits)
    assert all((s.jurisdiction or "").lower() == "india" for s in hits)
    assert any(s.section == "3(d)" for s in hits)


def test_international_filter_excludes_domestic_statutes():
    corpus = get_fixture_corpus()
    hits = filter_sources(
        corpus, jurisdiction="india", legal_scope=LegalScope.INTERNATIONAL
    )
    assert hits
    assert all(s.legal_scope == LegalScope.INTERNATIONAL for s in hits)
    assert not any(s.section in {"3(d)", "3(e)", "3(p)"} for s in hits)


def test_mock_retriever_domestic_query():
    retriever = get_mock_retriever()
    hits = retriever.retrieve(
        "Section 3 traditional knowledge Withania",
        jurisdiction="india",
        legal_scope="domestic",
    )
    assert hits
    ids = {s.id for s in hits}
    assert "fixture-in-s3p" in ids or "fixture-in-s3d" in ids
    assert all(s.is_fixture for s in hits)


def test_mock_retriever_international_query():
    retriever = get_mock_retriever()
    hits = retriever.retrieve(
        "comparative patentable subject matter",
        jurisdiction="india",
        legal_scope=LegalScope.INTERNATIONAL,
    )
    assert hits
    assert all(s.legal_scope == LegalScope.INTERNATIONAL for s in hits)


def test_international_empty_corpus_returns_empty():
    """Never invent foreign law — empty international corpus → no hits."""
    retriever = get_mock_retriever()
    domestic_only = [
        s for s in get_fixture_corpus() if s.legal_scope == LegalScope.DOMESTIC
    ]
    from retrieval.mock import MockLegalRetriever

    empty_intl = MockLegalRetriever(corpus=domestic_only)
    hits = empty_intl.retrieve(
        "TRIPS", jurisdiction="india", legal_scope=LegalScope.INTERNATIONAL
    )
    assert hits == []


def test_matches_scope_unset_source_scope_treated_as_domestic():
    from graph.models import RetrievedSource

    src = RetrievedSource(
        id="x",
        title="t",
        text="body",
        jurisdiction="india",
        legal_scope=None,
        is_fixture=True,
    )
    assert matches_scope_filters(
        src, jurisdiction="india", legal_scope=LegalScope.DOMESTIC
    )
    assert not matches_scope_filters(
        src, jurisdiction="india", legal_scope=LegalScope.INTERNATIONAL
    )
