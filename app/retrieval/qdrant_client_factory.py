"""Qdrant client construction (local embedded or remote/cloud) with config validation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from config import Settings

if TYPE_CHECKING:
    from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)

INGEST_COMMAND = "uv run python -m ingest.build_index --recreate"


class RetrievalConfigError(RuntimeError):
    """Raised when retrieval is misconfigured. Never silently fall back to mocks."""


def require_nvidia_api_key(settings: Settings) -> str:
    if not settings.nvidia_api_key:
        raise RetrievalConfigError(
            "NVIDIA_API_KEY is required for embedding-based retrieval."
        )
    return settings.nvidia_api_key


def create_qdrant_client(settings: Settings) -> "QdrantClient":
    """Build a QdrantClient for QDRANT_MODE=local|cloud.

    local: embedded on-disk DB at QDRANT_PATH (single process only).
    cloud: remote Qdrant over HTTP(S) — Qdrant Cloud or a self-hosted service.
    """
    from qdrant_client import QdrantClient

    mode = (settings.qdrant_mode or "").strip().lower()
    if mode == "local":
        logger.info("Qdrant mode=local path=%s", settings.qdrant_path)
        return QdrantClient(path=settings.qdrant_path)

    if mode == "cloud":
        if not settings.qdrant_url:
            raise RetrievalConfigError("QDRANT_URL is required when QDRANT_MODE=cloud.")
        if not settings.qdrant_api_key:
            raise RetrievalConfigError(
                "QDRANT_API_KEY is required when QDRANT_MODE=cloud."
            )
        host = urlparse(settings.qdrant_url).hostname or "<unparsed>"
        logger.info("Qdrant mode=cloud host=%s", host)
        return QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=30,
        )

    raise RetrievalConfigError(
        f"Unsupported QDRANT_MODE={settings.qdrant_mode!r}; expected 'local' or 'cloud'."
    )


def check_qdrant_connection(client: "QdrantClient", settings: Settings) -> None:
    """Fail fast on bad credentials / network. Error text never includes the key."""
    try:
        client.get_collections()
    except Exception as exc:  # noqa: BLE001
        raise RetrievalConfigError(
            f"Could not connect to Qdrant (mode={settings.qdrant_mode}): "
            f"{type(exc).__name__}. Check QDRANT_URL / QDRANT_API_KEY and network access."
        ) from exc


def ensure_collection_exists(client: "QdrantClient", collection: str) -> None:
    if not client.collection_exists(collection):
        raise RetrievalConfigError(
            f"Qdrant collection '{collection}' does not exist. "
            f"Run ingestion first: {INGEST_COMMAND}"
        )
