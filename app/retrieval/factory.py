"""Retriever factory: RETRIEVER_BACKEND=mock|qdrant. Never silently falls back to mock."""

from __future__ import annotations

import logging

from config import Settings, get_settings
from retrieval.base import LegalRetriever
from retrieval.mock import get_mock_retriever
from retrieval.qdrant_client_factory import RetrievalConfigError

logger = logging.getLogger(__name__)


def build_qdrant_retriever(settings: Settings) -> LegalRetriever:
    from retrieval.bm25_index import BM25Store
    from retrieval.embeddings import create_nvidia_embeddings
    from retrieval.qdrant_client_factory import (
        check_qdrant_connection,
        create_qdrant_client,
        ensure_collection_exists,
        require_nvidia_api_key,
    )
    from retrieval.qdrant_hybrid import QdrantHybridRetriever

    require_nvidia_api_key(settings)
    client = create_qdrant_client(settings)
    check_qdrant_connection(client, settings)
    ensure_collection_exists(client, settings.qdrant_collection)
    logger.info(
        "Qdrant retriever mode=%s collection=%s bm25_source=%s reranker=%s",
        settings.qdrant_mode,
        settings.qdrant_collection,
        settings.bm25_source,
        settings.reranker_enabled,
    )

    embeddings = create_nvidia_embeddings(settings)

    source = settings.bm25_source
    if source == "qdrant":
        bm25 = BM25Store.from_qdrant(client, settings.qdrant_collection)
    elif source == "file":
        bm25 = BM25Store.load(settings.bm25_dir)
    else:
        raise RetrievalConfigError(
            f"Unsupported BM25_SOURCE={source!r}; expected 'qdrant' or 'file'."
        )

    reranker = None
    if settings.reranker_enabled:
        from retrieval.rerank import NvidiaReranker

        reranker = NvidiaReranker(settings)

    return QdrantHybridRetriever(
        client,
        settings.qdrant_collection,
        embeddings,
        bm25,
        reranker=reranker,
        rrf_k=settings.rrf_k,
        dense_k=settings.dense_candidates,
        bm25_k=settings.bm25_candidates,
        rerank_k=settings.rerank_candidates,
    )


_retriever: LegalRetriever | None = None

def get_retriever(settings: Settings | None = None) -> LegalRetriever:
    global _retriever
    if _retriever is not None:
        return _retriever

    cfg = settings or get_settings()
    backend = (cfg.retriever_backend or "").strip().lower()
    logger.info("Retriever backend=%s", backend)
    if backend == "mock":
        _retriever = get_mock_retriever()
    elif backend == "qdrant":
        _retriever = build_qdrant_retriever(cfg)
    else:
        raise RetrievalConfigError(
            f"Unsupported RETRIEVER_BACKEND={cfg.retriever_backend!r}; expected 'mock' or 'qdrant'."
        )
    return _retriever
