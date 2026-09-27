"""Opt-in, read-only smoke test against the real Qdrant Cloud collection.

Runs only with RUN_CLOUD_TESTS=1 plus QDRANT_URL, QDRANT_API_KEY, NVIDIA_API_KEY.
Never ingests or modifies the collection.
"""

from __future__ import annotations

import os

import pytest

from config import Settings, get_settings

pytestmark = pytest.mark.cloud


def _cloud_settings() -> Settings:
    base = get_settings()
    return base.model_copy(update={"retriever_backend": "qdrant", "qdrant_mode": "cloud"})


@pytest.mark.skipif(
    os.getenv("RUN_CLOUD_TESTS") != "1"
    or not all(os.getenv(k) for k in ("QDRANT_URL", "QDRANT_API_KEY", "NVIDIA_API_KEY")),
    reason="cloud smoke test is opt-in (RUN_CLOUD_TESTS=1 + credentials)",
)
def test_cloud_hybrid_retrieval_smoke():
    from retrieval.factory import get_retriever

    retriever = get_retriever(_cloud_settings())
    hits = retriever.retrieve(
        "Section 3(d) known substance efficacy", jurisdiction="india", legal_scope="domestic"
    )
    for h in hits:
        assert h.legal_scope is None or h.legal_scope.value == "domestic"
