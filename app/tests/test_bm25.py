"""BM25 ranking, ID mapping, and persistence."""

from __future__ import annotations

import pytest

from graph.models import LegalScope
from retrieval.bm25_index import BM25_PICKLE, BM25Store, tokenize
from retrieval.chunks import CanonicalChunk
from retrieval.qdrant_client_factory import RetrievalConfigError


def _chunk(cid: str, text: str, **kw) -> CanonicalChunk:
    base = dict(
        title=cid,
        source_type="statute",
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
    )
    base.update(kw)
    return CanonicalChunk(id=cid, text=text, **base)


CORPUS = [
    _chunk("c_admixture", "mere admixture aggregation of properties"),
    _chunk("a_known", "new form of a known substance efficacy"),
    _chunk("b_tk", "traditional knowledge aggregation duplication"),
    _chunk("d_trademark", "brand trademark packaging design", source_type="guideline"),
]


def test_tokenize_keeps_clause_refs():
    assert "3(d)" in tokenize("Section 3(d) of the Act")
    assert "the" not in tokenize("the Act")


def test_bm25_ranks_relevant_first():
    store = BM25Store(CORPUS)
    hits = store.search("known substance efficacy", k=3)
    assert hits[0][0] == "a_known"
    assert all(score > 0 for _, score in hits)


def test_bm25_mapping_is_explicit_and_sorted():
    store = BM25Store(CORPUS)
    assert store.doc_ids == sorted(c.id for c in CORPUS)
    for pos, cid in enumerate(store.doc_ids):
        assert store.docs[cid].id == cid


def test_bm25_predicate_filters():
    store = BM25Store(CORPUS)
    hits = store.search(
        "aggregation trademark", k=10, predicate=lambda c: c.source_type == "guideline"
    )
    assert [cid for cid, _ in hits] == ["d_trademark"]


def test_save_load_roundtrip(tmp_path):
    BM25Store(CORPUS).save(tmp_path)
    loaded = BM25Store.load(tmp_path)
    assert loaded.doc_ids == sorted(c.id for c in CORPUS)
    assert loaded.search("traditional knowledge", k=1)[0][0] == "b_tk"


def test_rebuild_from_json_without_pickle(tmp_path):
    BM25Store(CORPUS).save(tmp_path)
    (tmp_path / BM25_PICKLE).unlink()
    loaded = BM25Store.load(tmp_path)
    assert loaded.search("mere admixture", k=1)[0][0] == "c_admixture"


def test_missing_index_explains_ingestion(tmp_path):
    with pytest.raises(RetrievalConfigError, match="ingest.build_index"):
        BM25Store.load(tmp_path)


def test_empty_corpus_rejected():
    with pytest.raises(RetrievalConfigError):
        BM25Store([])
