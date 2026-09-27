"""NVIDIA embedding / reranker construction (lazy imports, explicit key checks)."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from config import Settings
from retrieval.qdrant_client_factory import require_nvidia_api_key

logger = logging.getLogger(__name__)


class Embeddings(Protocol):
    """Subset of the LangChain Embeddings interface used here."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def create_nvidia_embeddings(settings: Settings) -> Any:
    """NVIDIAEmbeddings: embed_documents -> passage mode, embed_query -> query mode."""
    api_key = require_nvidia_api_key(settings)
    from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

    logger.info("Embedding model=%s", settings.embedding_model)
    return NVIDIAEmbeddings(
        model=settings.embedding_model,
        api_key=api_key,
        truncate="END",
    )


def probe_embedding_dimension(embeddings: Embeddings) -> int:
    """Determine vector size from the model itself (never hard-coded)."""
    try:
        dim = len(embeddings.embed_query("dimension probe"))
    except Exception as exc:  # noqa: BLE001
        model = getattr(embeddings, "model", "<unknown>")
        raise RuntimeError(
            f"Embedding model '{model}' failed ({str(exc).splitlines()[0][:200]}). "
            "If NVIDIA retired it, set EMBEDDING_MODEL to an available model."
        ) from exc
    if dim <= 0:
        raise RuntimeError("Embedding model returned an empty vector")
    return dim
