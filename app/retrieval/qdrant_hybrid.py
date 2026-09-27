"""Hybrid legal retriever: Qdrant dense search + BM25, fused with RRF, optional rerank."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from graph.models import LegalScope, RetrievedSource
from retrieval.base import coerce_legal_scope, matches_scope_filters
from retrieval.bm25_index import BM25Store
from retrieval.chunks import CanonicalChunk
from retrieval.embeddings import Embeddings
from retrieval.rerank import Reranker

if TYPE_CHECKING:
    from qdrant_client import QdrantClient, models

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], *, k: int = 60
) -> list[tuple[str, float]]:
    """RRF(d) = sum over rankings of 1 / (k + rank), rank starting at 1.

    Deduplicates by ID; ordering is deterministic (score desc, then ID asc).
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        seen: set[str] = set()
        for rank, doc_id in enumerate(ranking, start=1):
            if doc_id in seen:
                continue
            seen.add(doc_id)
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def _normalize_source_types(source_types: Sequence[str] | None) -> list[str] | None:
    if not source_types:
        return None
    return sorted({s.strip().lower() for s in source_types if s and s.strip()}) or None


def build_qdrant_filter(
    *,
    jurisdiction: str | None,
    legal_scope: LegalScope | str | None,
    source_types: Sequence[str] | None = None,
) -> "models.Filter":
    """Qdrant payload filter mirroring ``matches_scope_filters`` semantics."""
    from qdrant_client import models

    scope = coerce_legal_scope(legal_scope) or LegalScope.DOMESTIC
    must: list = [
        models.FieldCondition(key="legal_scope", match=models.MatchValue(value=scope.value))
    ]
    if scope == LegalScope.DOMESTIC and jurisdiction and jurisdiction.strip():
        must.append(
            models.Filter(
                should=[
                    models.FieldCondition(
                        key="jurisdiction",
                        match=models.MatchValue(value=jurisdiction.strip().lower()),
                    ),
                    models.IsEmptyCondition(is_empty=models.PayloadField(key="jurisdiction")),
                ]
            )
        )
    types = _normalize_source_types(source_types)
    if types:
        must.append(
            models.FieldCondition(key="source_type", match=models.MatchAny(any=types))
        )
    return models.Filter(must=must)


def make_chunk_predicate(
    *,
    jurisdiction: str | None,
    legal_scope: LegalScope | str | None,
    source_types: Sequence[str] | None = None,
) -> Callable[[CanonicalChunk], bool]:
    types = set(_normalize_source_types(source_types) or [])

    def _pred(chunk: CanonicalChunk) -> bool:
        if types and chunk.source_type.lower() not in types:
            return False
        return matches_scope_filters(
            chunk.to_retrieved_source(0.0),
            jurisdiction=jurisdiction,
            legal_scope=legal_scope,
        )

    return _pred


class QdrantHybridRetriever:
    """Implements ``LegalRetriever`` over Qdrant (local or cloud) + BM25."""

    def __init__(
        self,
        client: "QdrantClient",
        collection: str,
        embeddings: Embeddings,
        bm25_store: BM25Store,
        reranker: Reranker | None = None,
        *,
        rrf_k: int = 60,
        dense_k: int = 30,
        bm25_k: int = 30,
        rerank_k: int = 20,
    ) -> None:
        self._client = client
        self._collection = collection
        self._embeddings = embeddings
        self._bm25 = bm25_store
        self._reranker = reranker
        self._rrf_k = rrf_k
        self._dense_k = dense_k
        self._bm25_k = bm25_k
        self._rerank_k = rerank_k

    def _dense_search(
        self,
        query: str,
        qfilter: "models.Filter",
        predicate: Callable[[CanonicalChunk], bool],
    ) -> tuple[list[str], dict[str, CanonicalChunk]]:
        vector = self._embeddings.embed_query(query)
        response = self._client.query_points(
            collection_name=self._collection,
            query=vector,
            query_filter=qfilter,
            limit=self._dense_k,
            with_payload=True,
        )
        ids: list[str] = []
        chunks: dict[str, CanonicalChunk] = {}
        for point in response.points:
            chunk = CanonicalChunk.from_payload(point.payload or {})
            # Safety net: never return a source that violates the requested scope.
            if not predicate(chunk):
                continue
            ids.append(chunk.id)
            chunks[chunk.id] = chunk
        return ids, chunks

    def retrieve(
        self,
        query: str,
        *,
        jurisdiction: str = "india",
        legal_scope: LegalScope | str = LegalScope.DOMESTIC,
        top_k: int = 8,
        source_types: list[str] | None = None,
    ) -> list[RetrievedSource]:
        if not query or not query.strip() or top_k <= 0:
            return []

        qfilter = build_qdrant_filter(
            jurisdiction=jurisdiction, legal_scope=legal_scope, source_types=source_types
        )
        predicate = make_chunk_predicate(
            jurisdiction=jurisdiction, legal_scope=legal_scope, source_types=source_types
        )

        dense_ids, pool = self._dense_search(query, qfilter, predicate)
        bm25_hits = self._bm25.search(query, self._bm25_k, predicate)
        bm25_ids = [cid for cid, _ in bm25_hits]
        for cid in bm25_ids:
            pool.setdefault(cid, self._bm25.docs[cid])

        fused = reciprocal_rank_fusion([dense_ids, bm25_ids], k=self._rrf_k)
        logger.info(
            "Hybrid retrieval scope=%s jurisdiction=%s types=%s dense=%d bm25=%d fused=%d",
            coerce_legal_scope(legal_scope).value if legal_scope else "domestic",
            jurisdiction,
            source_types,
            len(dense_ids),
            len(bm25_ids),
            len(fused),
        )

        if self._reranker is not None and fused:
            candidates = [pool[cid] for cid, _ in fused[: self._rerank_k]]
            reranked = self._reranker.rerank(query, candidates)
            known = {c.id for c in candidates}
            ordered = [(cid, s) for cid, s in reranked if cid in known]
            logger.info("Reranked %d candidates", len(ordered))
            final = ordered[:top_k]
        else:
            final = fused[:top_k]

        return [pool[cid].to_retrieved_source(score) for cid, score in final]
