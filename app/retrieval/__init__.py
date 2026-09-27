"""Retrieval package: mock fixtures and Qdrant + BM25 hybrid (imported lazily)."""

from retrieval.base import LegalRetriever, filter_sources, matches_scope_filters
from retrieval.factory import get_retriever
from retrieval.mock import MockLegalRetriever, get_fixture_corpus, get_mock_retriever
from retrieval.qdrant_client_factory import RetrievalConfigError

__all__ = [
    "LegalRetriever",
    "MockLegalRetriever",
    "RetrievalConfigError",
    "filter_sources",
    "get_fixture_corpus",
    "get_mock_retriever",
    "get_retriever",
    "matches_scope_filters",
]
