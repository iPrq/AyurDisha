"""End-to-end hybrid retrieval over an in-memory Qdrant built from ingestion fixtures."""

from __future__ import annotations

import json

import pytest

from graph.models import LegalScope, RetrievedSource
from retrieval.base import LegalRetriever, matches_scope_filters
from retrieval.bm25_index import BM25Store
from retrieval.qdrant_hybrid import QdrantHybridRetriever, build_qdrant_filter


def _retriever(idx, **kw) -> QdrantHybridRetriever:
    return QdrantHybridRetriever(
        idx["client"],
        idx["collection"],
        idx["embeddings"],
        BM25Store.load(idx["processed_dir"]),
        **kw,
    )


def test_satisfies_protocol(indexed_qdrant):
    assert isinstance(_retriever(indexed_qdrant), LegalRetriever)


def test_collection_holds_all_chunks(indexed_qdrant):
    count = indexed_qdrant["client"].count(indexed_qdrant["collection"], exact=True).count
    assert count == len(indexed_qdrant["chunks"])


def test_domestic_india_results(indexed_qdrant):
    hits = _retriever(indexed_qdrant).retrieve(
        "Section 3(d) known substance efficacy",
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
    )
    assert hits
    assert hits[0].id == "fixture_patents_act_3_d"
    assert all(h.legal_scope == LegalScope.DOMESTIC for h in hits)
    assert all(h.jurisdiction == "india" for h in hits)


def test_india_source_excluded_for_epo_domestic(indexed_qdrant):
    hits = _retriever(indexed_qdrant).retrieve(
        "Section 3(d) known substance traditional knowledge",
        jurisdiction="epo",
        legal_scope=LegalScope.DOMESTIC,
    )
    assert not any(h.jurisdiction == "india" for h in hits)


def test_international_never_returns_domestic(indexed_qdrant):
    hits = _retriever(indexed_qdrant).retrieve(
        "Section 3(d) traditional knowledge herbal composition patentable",
        jurisdiction="india",
        legal_scope=LegalScope.INTERNATIONAL,
    )
    assert hits
    assert all(h.legal_scope == LegalScope.INTERNATIONAL for h in hits)
    assert not any(h.jurisdiction == "india" for h in hits)
    assert not any((h.section or "").startswith("3(") for h in hits)


def test_dense_filter_alone_respects_scope(indexed_qdrant):
    idx = indexed_qdrant
    vec = idx["embeddings"].embed_query("Section 3(d) traditional knowledge")
    points = idx["client"].query_points(
        idx["collection"],
        query=vec,
        query_filter=build_qdrant_filter(
            jurisdiction="india", legal_scope=LegalScope.INTERNATIONAL
        ),
        limit=50,
    ).points
    assert points
    assert all(p.payload["legal_scope"] == "international" for p in points)


def test_source_type_filter_patent(indexed_qdrant):
    hits = _retriever(indexed_qdrant).retrieve(
        "Withania somnifera withanolides composition",
        source_types=["patent"],
    )
    assert hits
    assert all(h.source_type == "patent" for h in hits)


def test_source_type_filter_statute_or_guideline(indexed_qdrant):
    hits = _retriever(indexed_qdrant).retrieve(
        "Withania somnifera admixture traditional knowledge",
        source_types=["statute", "guideline"],
    )
    assert hits
    assert {h.source_type for h in hits} <= {"statute", "guideline"}


def test_results_are_retrieved_sources(indexed_qdrant):
    hits = _retriever(indexed_qdrant).retrieve("trademark packaging trade secret", top_k=3)
    assert 0 < len(hits) <= 3
    for h in hits:
        assert isinstance(h, RetrievedSource)
        assert h.title and h.text and h.source_type
        assert h.retrieval_score > 0
        # fixtures are flagged from payload
        assert h.is_fixture is True
        assert matches_scope_filters(h, jurisdiction="india", legal_scope="domestic")
    scores = [h.retrieval_score for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_no_duplicate_ids(indexed_qdrant):
    hits = _retriever(indexed_qdrant).retrieve(
        "Withania somnifera withanolides traditional knowledge", top_k=20
    )
    ids = [h.id for h in hits]
    assert len(ids) == len(set(ids))


def test_query_embedding_used(indexed_qdrant):
    emb = indexed_qdrant["embeddings"]
    before = emb.query_calls
    _retriever(indexed_qdrant).retrieve("admixture")
    assert emb.query_calls == before + 1


def test_bm25_from_qdrant_matches_file(indexed_qdrant):
    idx = indexed_qdrant
    from_file = BM25Store.load(idx["processed_dir"])
    from_qdrant = BM25Store.from_qdrant(idx["client"], idx["collection"])
    assert from_file.doc_ids == from_qdrant.doc_ids


def test_reranker_reorders(indexed_qdrant):
    class ReverseReranker:
        def rerank(self, query, chunks):
            return [(c.id, float(i)) for i, c in enumerate(reversed(chunks))]

    base = _retriever(indexed_qdrant).retrieve("Section 3 admixture", top_k=20)
    reranked = _retriever(indexed_qdrant, reranker=ReverseReranker()).retrieve(
        "Section 3 admixture", top_k=20
    )
    assert [h.id for h in reranked] == list(reversed([h.id for h in base]))


def test_empty_query_returns_empty(indexed_qdrant):
    assert _retriever(indexed_qdrant).retrieve("   ") == []


def test_real_source_is_not_fixture(tmp_path, fake_embeddings):
    from qdrant_client import QdrantClient

    from ingest.build_index import build_index

    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "act.txt").write_text(
        "3. Heading.—\n(d) clause about known substance efficacy.\n(e) admixture clause.",
        encoding="utf-8",
    )
    (raw / "act.meta.json").write_text(
        json.dumps(
            {
                "doc_id": "sample_act",
                "title": "Sample Act",
                "source_type": "statute",
                "jurisdiction": "india",
                "legal_scope": "domestic",
            }
        ),
        encoding="utf-8",
    )
    client = QdrantClient(location=":memory:")
    try:
        build_index(
            client=client,
            embeddings=fake_embeddings,
            collection="real",
            raw_dir=raw,
            processed_dir=tmp_path / "processed",
            recreate=True,
        )
        retriever = QdrantHybridRetriever(
            client, "real", fake_embeddings, BM25Store.load(tmp_path / "processed")
        )
        hits = retriever.retrieve("known substance efficacy")
        assert hits
        assert all(h.is_fixture is False for h in hits)
    finally:
        client.close()


def test_dimension_mismatch_requires_recreate(indexed_qdrant, tmp_path):
    from ingest.build_index import ensure_collection

    with pytest.raises(RuntimeError, match="--recreate"):
        ensure_collection(
            indexed_qdrant["client"], indexed_qdrant["collection"], 128, recreate=False
        )
