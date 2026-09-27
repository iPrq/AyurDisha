"""Retriever factory selection and fail-loud behaviour."""

from __future__ import annotations

import pytest

import retrieval.embeddings as embeddings_mod
import retrieval.qdrant_client_factory as qcf
from config import Settings
from retrieval.factory import get_retriever
from retrieval.mock import MockLegalRetriever
from retrieval.qdrant_client_factory import RetrievalConfigError
from retrieval.qdrant_hybrid import QdrantHybridRetriever


def test_mock_backend_default():
    retriever = get_retriever(Settings())
    assert isinstance(retriever, MockLegalRetriever)
    hits = retriever.retrieve("Section 3", jurisdiction="india", legal_scope="domestic")
    assert hits and all(h.is_fixture for h in hits)


def test_mock_source_types_filter():
    hits = get_retriever(Settings()).retrieve(
        "Section 3 traditional knowledge", source_types=["statute"]
    )
    assert hits
    assert all(h.source_type == "statute_fixture" for h in hits)


def test_unknown_backend_rejected():
    with pytest.raises(RetrievalConfigError, match="RETRIEVER_BACKEND"):
        get_retriever(Settings(retriever_backend="elastic"))


def test_qdrant_backend_requires_nvidia_key(tmp_path):
    with pytest.raises(RetrievalConfigError, match="NVIDIA_API_KEY"):
        get_retriever(
            Settings(
                retriever_backend="qdrant",
                qdrant_mode="local",
                qdrant_path=str(tmp_path / "qd"),
                nvidia_api_key=None,
            )
        )


def test_qdrant_backend_does_not_fall_back_to_mock_on_bad_cloud_config():
    with pytest.raises(RetrievalConfigError, match="QDRANT_URL"):
        get_retriever(
            Settings(retriever_backend="qdrant", qdrant_mode="cloud", nvidia_api_key="k")
        )


def _patch_qdrant(monkeypatch, indexed_qdrant, fake_embeddings):
    monkeypatch.setattr(qcf, "create_qdrant_client", lambda s: indexed_qdrant["client"])
    monkeypatch.setattr(
        embeddings_mod, "create_nvidia_embeddings", lambda s: fake_embeddings
    )


def test_qdrant_backend_selected(monkeypatch, indexed_qdrant, fake_embeddings):
    _patch_qdrant(monkeypatch, indexed_qdrant, fake_embeddings)

    def _boom(*a, **k):
        raise AssertionError("reranker must not be constructed when disabled")

    import retrieval.rerank as rerank_mod

    monkeypatch.setattr(rerank_mod, "NvidiaReranker", _boom)

    retriever = get_retriever(
        Settings(
            retriever_backend="qdrant",
            qdrant_collection=indexed_qdrant["collection"],
            nvidia_api_key="test-key",
            bm25_source="qdrant",
            reranker_enabled=False,
        )
    )
    assert isinstance(retriever, QdrantHybridRetriever)
    hits = retriever.retrieve("Section 3(e) admixture")
    assert hits and hits[0].id == "fixture_patents_act_3_e"


def test_qdrant_backend_bm25_file_source(monkeypatch, indexed_qdrant, fake_embeddings):
    _patch_qdrant(monkeypatch, indexed_qdrant, fake_embeddings)
    retriever = get_retriever(
        Settings(
            retriever_backend="qdrant",
            qdrant_collection=indexed_qdrant["collection"],
            nvidia_api_key="test-key",
            bm25_source="file",
            bm25_dir=str(indexed_qdrant["processed_dir"]),
        )
    )
    assert isinstance(retriever, QdrantHybridRetriever)


def test_qdrant_backend_missing_collection(monkeypatch, indexed_qdrant, fake_embeddings):
    _patch_qdrant(monkeypatch, indexed_qdrant, fake_embeddings)
    with pytest.raises(RetrievalConfigError, match="ingest.build_index"):
        get_retriever(
            Settings(
                retriever_backend="qdrant",
                qdrant_collection="does_not_exist",
                nvidia_api_key="test-key",
            )
        )


def test_enabled_reranker_with_bad_config_fails(monkeypatch, indexed_qdrant, fake_embeddings):
    _patch_qdrant(monkeypatch, indexed_qdrant, fake_embeddings)
    import retrieval.rerank as rerank_mod

    def _broken(settings):
        raise RetrievalConfigError("reranker could not be initialised")

    monkeypatch.setattr(rerank_mod, "NvidiaReranker", _broken)
    with pytest.raises(RetrievalConfigError, match="reranker"):
        get_retriever(
            Settings(
                retriever_backend="qdrant",
                qdrant_collection=indexed_qdrant["collection"],
                nvidia_api_key="test-key",
                reranker_enabled=True,
            )
        )
