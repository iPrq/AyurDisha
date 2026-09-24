"""Retrieval package (mock now; Qdrant/BM25 hybrid later)."""

from retrieval.base import LegalRetriever, filter_sources, matches_scope_filters
from retrieval.mock import MockLegalRetriever, get_fixture_corpus, get_mock_retriever

__all__ = [
    "LegalRetriever",
    "MockLegalRetriever",
    "filter_sources",
    "get_fixture_corpus",
    "get_mock_retriever",
    "matches_scope_filters",
]
