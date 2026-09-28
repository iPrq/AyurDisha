"""Exact Section 3 clause retrieval (BM25 + Qdrant + RRF) and the focused statute retrieval step.

Index built from placeholder fixtures only (no statutory wording).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from config import Settings
from graph.models import SUPPORTED_SECTION3_CLAUSES, LegalScope
from graph.patent_advisor.retrieval import legal_patent_retrieval_node
from retrieval.bm25_index import BM25Store, tokenize
from retrieval.mock import MockLegalRetriever, get_mock_retriever
from retrieval.qdrant_hybrid import QdrantHybridRetriever

PLACEHOLDER_DIR = Path(__file__).resolve().parent / "fixtures" / "section3_placeholder"


@pytest.fixture(scope="module")
def s3_index(tmp_path_factory):
    from qdrant_client import QdrantClient

    from ingest.build_index import build_index
    from tests.conftest import FakeEmbeddings

    tmp = tmp_path_factory.mktemp("s3idx")
    emb = FakeEmbeddings()
    client = QdrantClient(location=":memory:")
    build_index(
        client=client,
        embeddings=emb,
        collection="s3",
        raw_dir=PLACEHOLDER_DIR,
        processed_dir=tmp / "processed",
        recreate=True,
    )
    retriever = QdrantHybridRetriever(
        client, "s3", emb, BM25Store.load(tmp / "processed")
    )
    try:
        yield {"retriever": retriever, "bm25": BM25Store.load(tmp / "processed")}
    finally:
        client.close()


@pytest.mark.parametrize("ref", SUPPORTED_SECTION3_CLAUSES)
def test_tokenizer_keeps_every_supported_clause_ref(ref):
    assert tokenize(f"Section {ref} applies") == ["section", ref, "applies"]


@pytest.mark.parametrize("ref", SUPPORTED_SECTION3_CLAUSES)
def test_bm25_exact_clause_ranks_first(s3_index, ref):
    hits = s3_index["bm25"].search(ref, k=3)
    assert hits and hits[0][0] == f"fixture_s3_placeholder_3_{ref[2]}"


@pytest.mark.parametrize("ref", SUPPORTED_SECTION3_CLAUSES)
def test_hybrid_retrieves_each_clause(s3_index, ref):
    hits = s3_index["retriever"].retrieve(
        f"Section {ref}", jurisdiction="india", legal_scope="domestic", top_k=3
    )
    assert hits[0].section == ref


@pytest.mark.parametrize("ref", ["3(a)", "3(c)", "3(k)", "3(p)"])
def test_bare_clause_query_ranks_clause_evidence(s3_index, ref):
    hits = s3_index["retriever"].retrieve(ref, top_k=5)
    assert hits[0].section == ref


def test_no_3g_retrievable(s3_index):
    hits = s3_index["retriever"].retrieve("Section 3(g)", top_k=20)
    assert not any(h.section == "3(g)" for h in hits)


def test_focused_statute_query_returns_all_fifteen_clauses(s3_index):
    update = legal_patent_retrieval_node(
        {
            "product": "Ashwagandha capsule",
            "ingredients": ["Ashwagandha"],
            "language": "en",
            "jurisdiction": "india",
            "legal_scope": "domestic",
            "botanical_name": "Withania somnifera",
        },
        retriever=s3_index["retriever"],
        settings=Settings(),
    )
    sections = [s.section for s in update["retrieved_sources"]]
    assert set(SUPPORTED_SECTION3_CLAUSES) <= set(sections)


def test_focused_retrieval_drops_non_section3_statute_chunks():
    from graph.models import RetrievedSource

    def _src(sid, section):
        return RetrievedSource(
            id=sid, title=sid, text="t", section=section, source_type="statute",
            jurisdiction="india", legal_scope=LegalScope.DOMESTIC, is_fixture=True,
        )

    class Fixed:
        def retrieve(self, query, *, source_types=None, **kw):
            if not source_types:
                return []
            return [_src("a", "3(k)"), _src("b", "4"), _src("c", "3(g)"), _src("d", "3")]

    update = legal_patent_retrieval_node(_state(), retriever=Fixed(), settings=Settings())
    assert [s.id for s in update["retrieved_sources"]] == ["a", "d"]


# ---------------------------------------------------------------------------
# Retrieval node behaviour
# ---------------------------------------------------------------------------


class RecordingRetriever:
    def __init__(self, inner):
        self.inner = inner
        self.calls: list[dict] = []

    def retrieve(self, query, **kwargs):
        self.calls.append({"query": query, **kwargs})
        return self.inner.retrieve(query, **kwargs)


def _state(scope="domestic", jurisdiction="india"):
    return {
        "product": "Ashwagandha capsule",
        "ingredients": ["Ashwagandha"],
        "language": "en",
        "jurisdiction": jurisdiction,
        "legal_scope": scope,
        "botanical_name": "Withania somnifera",
    }


def test_domestic_performs_focused_statute_retrieval():
    rec = RecordingRetriever(get_mock_retriever())
    legal_patent_retrieval_node(
        _state(), retriever=rec,
        settings=Settings(section3_statute_top_k=30, dense_candidates=30, bm25_candidates=30),
    )
    assert len(rec.calls) == 2
    focused = rec.calls[1]
    assert focused["source_types"] == ["statute"]
    assert focused["top_k"] == 60  # never below dense + BM25 candidates
    for ref in SUPPORTED_SECTION3_CLAUSES:
        assert ref in focused["query"]
    assert "3(g)" not in focused["query"]


def test_international_skips_domestic_statute_retrieval():
    rec = RecordingRetriever(get_mock_retriever())
    update = legal_patent_retrieval_node(
        _state(scope=LegalScope.INTERNATIONAL), retriever=rec, settings=Settings()
    )
    assert len(rec.calls) == 1
    assert "source_types" not in rec.calls[0]
    assert all(s.legal_scope == LegalScope.INTERNATIONAL for s in update["retrieved_sources"])


def test_non_india_domestic_skips_statute_retrieval():
    rec = RecordingRetriever(get_mock_retriever())
    legal_patent_retrieval_node(_state(jurisdiction="epo"), retriever=rec, settings=Settings())
    assert len(rec.calls) == 1


def test_merge_has_no_duplicates_and_keeps_broad_order():
    retriever = get_mock_retriever()
    broad = retriever.retrieve(
        "Withania somnifera Ashwagandha capsule Ashwagandha Section 3 patent traditional knowledge",
        jurisdiction="india",
        legal_scope="domestic",
    )
    update = legal_patent_retrieval_node(_state(), retriever=retriever, settings=Settings())
    ids = [s.id for s in update["retrieved_sources"]]
    assert len(ids) == len(set(ids))
    assert ids[: len(broad)] == [s.id for s in broad]


def test_existing_mock_retrieval_result_unchanged():
    """Mock statute fixtures are already in the broad results, so output is unchanged."""
    retriever = get_mock_retriever()
    before = retriever.retrieve(
        "Withania somnifera Ashwagandha capsule Ashwagandha Section 3 patent traditional knowledge",
        jurisdiction="india",
        legal_scope="domestic",
    )
    update = legal_patent_retrieval_node(_state(), retriever=retriever, settings=Settings())
    assert [s.id for s in update["retrieved_sources"]] == [s.id for s in before]
    assert update["retrieval_insufficient"] is False


def test_statute_only_hits_rescue_empty_broad_retrieval():
    class StatuteOnly:
        def retrieve(self, query, *, source_types=None, **kw):
            if source_types:
                return MockLegalRetriever().retrieve(query, source_types=source_types, **kw)
            return []

    update = legal_patent_retrieval_node(_state(), retriever=StatuteOnly(), settings=Settings())
    assert update["retrieved_sources"]
    assert update["retrieval_insufficient"] is False
    assert "escalation_reasons" not in update
