"""Qdrant client configuration (local + cloud validation). No network."""

from __future__ import annotations

import pytest

from config import Settings
from retrieval.qdrant_client_factory import (
    RetrievalConfigError,
    create_qdrant_client,
    ensure_collection_exists,
    require_nvidia_api_key,
)

SECRET = "super-secret-qdrant-key"


def test_local_client_initialises(tmp_path):
    client = create_qdrant_client(
        Settings(qdrant_mode="local", qdrant_path=str(tmp_path / "qd"))
    )
    try:
        assert client.get_collections().collections == []
    finally:
        client.close()


def test_cloud_requires_url():
    with pytest.raises(RetrievalConfigError, match="QDRANT_URL is required"):
        create_qdrant_client(Settings(qdrant_mode="cloud", qdrant_api_key=SECRET))


def test_cloud_requires_api_key():
    with pytest.raises(RetrievalConfigError, match="QDRANT_API_KEY is required"):
        create_qdrant_client(
            Settings(qdrant_mode="cloud", qdrant_url="https://x.cloud.qdrant.io:6333")
        )


def test_cloud_passes_url_and_key(monkeypatch):
    captured: dict = {}

    class DummyClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    import qdrant_client

    monkeypatch.setattr(qdrant_client, "QdrantClient", DummyClient)
    create_qdrant_client(
        Settings(
            qdrant_mode="cloud",
            qdrant_url="https://abc.cloud.qdrant.io:6333",
            qdrant_api_key=SECRET,
        )
    )
    assert captured["url"] == "https://abc.cloud.qdrant.io:6333"
    assert captured["api_key"] == SECRET
    assert "path" not in captured


def test_unknown_mode_rejected():
    with pytest.raises(RetrievalConfigError, match="Unsupported QDRANT_MODE"):
        create_qdrant_client(Settings(qdrant_mode="bogus"))


def test_missing_nvidia_key_message():
    with pytest.raises(
        RetrievalConfigError,
        match="NVIDIA_API_KEY is required for embedding-based retrieval.",
    ):
        require_nvidia_api_key(Settings(nvidia_api_key=None))


def test_missing_collection_explains_ingestion():
    from qdrant_client import QdrantClient

    client = QdrantClient(location=":memory:")
    with pytest.raises(RetrievalConfigError, match="ingest.build_index"):
        ensure_collection_exists(client, "nope")


def test_redacted_settings_hide_secrets():
    s = Settings(nvidia_api_key="nv-secret", qdrant_api_key=SECRET)
    dumped = str(s.redacted())
    assert SECRET not in dumped
    assert "nv-secret" not in dumped
