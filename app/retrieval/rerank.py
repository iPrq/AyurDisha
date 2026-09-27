"""Optional NVIDIA reranker (only constructed when RERANKER_ENABLED=true)."""

from __future__ import annotations

import logging
from typing import Protocol

from config import Settings
from retrieval.chunks import CanonicalChunk
from retrieval.qdrant_client_factory import RetrievalConfigError, require_nvidia_api_key

logger = logging.getLogger(__name__)


class Reranker(Protocol):
    def rerank(self, query: str, chunks: list[CanonicalChunk]) -> list[tuple[str, float]]:
        """Return (chunk_id, relevance) pairs, best first."""
        ...


class NvidiaReranker:
    def __init__(self, settings: Settings) -> None:
        api_key = require_nvidia_api_key(settings)
        try:
            from langchain_nvidia_ai_endpoints import NVIDIARerank

            self._model = NVIDIARerank(
                model=settings.rerank_model,
                api_key=api_key,
                top_n=max(settings.rerank_candidates, 1),
                truncate="END",
            )
        except Exception as exc:  # noqa: BLE001
            raise RetrievalConfigError(
                f"RERANKER_ENABLED=true but the NVIDIA reranker "
                f"'{settings.rerank_model}' could not be initialised: {type(exc).__name__}"
            ) from exc
        logger.info("Reranker enabled model=%s", settings.rerank_model)

    def rerank(self, query: str, chunks: list[CanonicalChunk]) -> list[tuple[str, float]]:
        from langchain_core.documents import Document

        if not chunks:
            return []
        docs = [
            Document(page_content=c.index_text(), metadata={"chunk_id": c.id})
            for c in chunks
        ]
        ranked = self._model.compress_documents(documents=docs, query=query)
        return [
            (d.metadata["chunk_id"], float(d.metadata.get("relevance_score", 0.0)))
            for d in ranked
        ]
