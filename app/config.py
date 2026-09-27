"""Environment-backed settings for AyurDisha backend."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

DEFAULT_EMBEDDING_MODEL = "nvidia/nemotron-3-embed-1b"
DEFAULT_RERANK_MODEL = "nvidia/llama-nemotron-rerank-vl-1b-v2"


class Settings(BaseModel):
    """Shared runtime configuration (LLM, scoring weights, thresholds)."""

    # NVIDIA NIM (primary)
    nvidia_api_key: str | None = Field(default=None)
    nvidia_base_url: str = Field(default="https://integrate.api.nvidia.com/v1")
    llm_model: str = Field(default="meta/llama-3.1-70b-instruct")
    llm_temperature: float = Field(default=0.0)

    # Defaults for Patent Advisor requests
    default_jurisdiction: str = Field(default="india")
    default_language: str = Field(default="en")
    default_legal_scope: str = Field(default="domestic")

    # Deterministic Section 3 patentability risk weights (decision-support only)
    section3_weight_d: float = Field(default=0.35)
    section3_weight_e: float = Field(default=0.30)
    section3_weight_p: float = Field(default=0.35)

    # Focused Section 3 statute retrieval (domestic India only): minimum candidate count
    # requested from the hybrid retriever (raised to DENSE_CANDIDATES + BM25_CANDIDATES
    # if smaller); results are then restricted to Section 3 chunks.
    section3_statute_top_k: int = Field(default=30)

    # Confidence / escalation placeholders
    botanical_confidence_threshold: float = Field(default=0.7)
    verification_min_support_ratio: float = Field(default=0.6)
    max_verifier_retries: int = Field(default=1)

    # Retrieval backend (mock by default; qdrant = Qdrant dense + BM25 hybrid)
    retriever_backend: str = Field(default="mock")
    qdrant_mode: str = Field(default="local")
    qdrant_path: str = Field(default="./qdrant_data")
    qdrant_url: str | None = Field(default=None)
    qdrant_api_key: str | None = Field(default=None)
    qdrant_collection: str = Field(default="ayurdisha_legal")

    # nv-embedqa-e5-v5 / nv-rerankqa-mistral-4b-v3 were retired by NVIDIA (410/404).
    embedding_model: str = Field(default=DEFAULT_EMBEDDING_MODEL)
    rerank_model: str = Field(default=DEFAULT_RERANK_MODEL)
    reranker_enabled: bool = Field(default=False)

    # BM25: "qdrant" rebuilds from collection payloads; "file" loads bm25_dir
    bm25_source: str = Field(default="qdrant")
    bm25_dir: str = Field(default="./data/processed")

    rrf_k: int = Field(default=60)
    dense_candidates: int = Field(default=30)
    bm25_candidates: int = Field(default=30)
    rerank_candidates: int = Field(default=20)

    def redacted(self) -> dict[str, object]:
        """Settings dump safe for logs (secrets masked)."""
        data = self.model_dump()
        for key in ("nvidia_api_key", "qdrant_api_key"):
            data[key] = "***" if data.get(key) else None
        return data


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_str(name: str, default: str | None = None) -> str | None:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings from environment (via dotenv) once per process."""
    return Settings(
        nvidia_api_key=os.getenv("NVIDIA_API_KEY") or os.getenv("NIM_API_KEY") or None,
        nvidia_base_url=os.getenv(
            "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
        ),
        llm_model=os.getenv(
            "LLM_MODEL",
            os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct"),
        ),
        llm_temperature=_env_float("LLM_TEMPERATURE", 0.0),
        default_jurisdiction=os.getenv("DEFAULT_JURISDICTION", "india"),
        default_language=os.getenv("DEFAULT_LANGUAGE", "en"),
        default_legal_scope=os.getenv("DEFAULT_LEGAL_SCOPE", "domestic"),
        section3_weight_d=_env_float("SECTION3_WEIGHT_D", 0.35),
        section3_weight_e=_env_float("SECTION3_WEIGHT_E", 0.30),
        section3_weight_p=_env_float("SECTION3_WEIGHT_P", 0.35),
        section3_statute_top_k=_env_int("SECTION3_STATUTE_TOP_K", 30),
        botanical_confidence_threshold=_env_float(
            "BOTANICAL_CONFIDENCE_THRESHOLD", 0.7
        ),
        verification_min_support_ratio=_env_float(
            "VERIFICATION_MIN_SUPPORT_RATIO", 0.6
        ),
        max_verifier_retries=_env_int("MAX_VERIFIER_RETRIES", 1),
        retriever_backend=(_env_str("RETRIEVER_BACKEND", "mock") or "mock").lower(),
        qdrant_mode=(_env_str("QDRANT_MODE", "local") or "local").lower(),
        qdrant_path=_env_str("QDRANT_PATH", "./qdrant_data") or "./qdrant_data",
        qdrant_url=_env_str("QDRANT_URL"),
        qdrant_api_key=_env_str("QDRANT_API_KEY"),
        qdrant_collection=_env_str("QDRANT_COLLECTION", "ayurdisha_legal")
        or "ayurdisha_legal",
        embedding_model=_env_str("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        or DEFAULT_EMBEDDING_MODEL,
        rerank_model=_env_str("RERANK_MODEL", DEFAULT_RERANK_MODEL) or DEFAULT_RERANK_MODEL,
        reranker_enabled=_env_bool("RERANKER_ENABLED", False),
        bm25_source=(_env_str("BM25_SOURCE", "qdrant") or "qdrant").lower(),
        bm25_dir=_env_str("BM25_DIR", "./data/processed") or "./data/processed",
        rrf_k=_env_int("RRF_K", 60),
        dense_candidates=_env_int("DENSE_CANDIDATES", 30),
        bm25_candidates=_env_int("BM25_CANDIDATES", 30),
        rerank_candidates=_env_int("RERANK_CANDIDATES", 20),
    )
