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
    # ChatNVIDIA defaults to 1024, which truncates large structured replies.
    llm_max_tokens: int = Field(default=8192)
    # Reasoning models (e.g. Nemotron 3) otherwise spend the token budget thinking before the JSON.
    llm_thinking: bool = Field(default=False)
    # Tried in order when the primary model errors (e.g. 503 overloaded).
    llm_fallback_models: list[str] = Field(default_factory=list)
    # Retries per LLM call on transient errors (429 / 5xx / timeouts), exponential backoff.
    llm_max_retries: int = Field(default=3)

    # Groq (last-resort fallback after every NVIDIA model, or sole provider without NVIDIA)
    groq_api_key: str | None = Field(default=None)
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1")
    groq_model: str = Field(default="llama-3.3-70b-versatile")
    groq_timeout: float = Field(default=120.0)

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

    # Web search (Product Review evidence): mock | serper | google_cse | tavily | none
    web_search_backend: str = Field(default="mock")
    serper_api_key: str | None = Field(default=None)
    google_cse_api_key: str | None = Field(default=None)
    google_cse_id: str | None = Field(default=None)
    tavily_api_key: str | None = Field(default=None)
    web_search_results: int = Field(default=5)
    web_search_timeout: float = Field(default=15.0)
    web_search_country: str = Field(default="in")

    # Product Review: cap on ingredients searched for resource accessibility
    product_review_max_resources: int = Field(default=3)

    # PDF upload (Patent Advisor): text layer first, local RapidOCR for scanned pages
    pdf_max_bytes: int = Field(default=20 * 1024 * 1024)
    pdf_max_pages: int = Field(default=30)
    pdf_ocr_enabled: bool = Field(default=True)
    pdf_ocr_min_chars: int = Field(default=50)
    pdf_ocr_dpi: int = Field(default=200)
    # Max document characters passed into Patent Advisor prompts
    patent_doc_context_chars: int = Field(default=12000)

    # Knowledge graph: neo4j (when NEO4J_URI is set) or an in-memory fallback
    kg_backend: str = Field(default="memory")
    neo4j_uri: str | None = Field(default=None)
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str | None = Field(default=None)
    neo4j_database: str | None = Field(default=None)
    # Seed curated herbs + corpus mentions at startup when the graph is empty
    kg_auto_seed: bool = Field(default=True)
    kg_corpus_dir: str = Field(default="./data/raw/corpus")
    # Write each pipeline response (product, herbs, sources) into the graph
    kg_record_responses: bool = Field(default=True)

    # BHASHINI (optional language / voice layer). Service IDs are discovered, not configured,
    # unless an explicit override is set.
    bhashini_enabled: bool = Field(default=False)
    bhashini_user_id: str | None = Field(default=None)
    bhashini_api_key: str | None = Field(default=None)
    bhashini_base_url: str = Field(
        default="https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
    )
    bhashini_pipeline_id: str | None = Field(default="64392f96daac500b55c543cd")
    bhashini_default_source_language: str = Field(default="en")
    bhashini_default_target_language: str = Field(default="en")
    bhashini_asr_service: str | None = Field(default=None)
    bhashini_translation_service: str | None = Field(default=None)
    bhashini_tts_service: str | None = Field(default=None)
    bhashini_timeout: float = Field(default=20.0)
    audio_max_bytes: int = Field(default=5 * 1024 * 1024)

    def redacted(self) -> dict[str, object]:
        """Settings dump safe for logs (secrets masked)."""
        data = self.model_dump()
        for key in (
            "nvidia_api_key",
            "groq_api_key",
            "qdrant_api_key",
            "serper_api_key",
            "google_cse_api_key",
            "tavily_api_key",
            "neo4j_password",
            "bhashini_api_key",
            "bhashini_user_id",
        ):
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
        llm_max_tokens=_env_int("LLM_MAX_TOKENS", 8192),
        llm_thinking=_env_bool("LLM_THINKING", False),
        llm_fallback_models=[
            m.strip() for m in os.getenv("LLM_FALLBACK_MODELS", "").split(",") if m.strip()
        ],
        llm_max_retries=_env_int("LLM_MAX_RETRIES", 3),
        groq_api_key=_env_str("GROQ_API_KEY"),
        groq_base_url=_env_str("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        or "https://api.groq.com/openai/v1",
        groq_model=_env_str("GROQ_MODEL", "llama-3.3-70b-versatile") or "llama-3.3-70b-versatile",
        groq_timeout=_env_float("GROQ_TIMEOUT", 120.0),
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
        web_search_backend=(_env_str("WEB_SEARCH_BACKEND", "mock") or "mock").lower(),
        serper_api_key=_env_str("SERPER_API_KEY"),
        google_cse_api_key=_env_str("GOOGLE_CSE_API_KEY"),
        google_cse_id=_env_str("GOOGLE_CSE_ID"),
        tavily_api_key=_env_str("TAVILY_API_KEY"),
        web_search_results=_env_int("WEB_SEARCH_RESULTS", 5),
        web_search_timeout=_env_float("WEB_SEARCH_TIMEOUT", 15.0),
        web_search_country=(_env_str("WEB_SEARCH_COUNTRY", "in") or "in").lower(),
        product_review_max_resources=_env_int("PRODUCT_REVIEW_MAX_RESOURCES", 3),
        pdf_max_bytes=_env_int("PDF_MAX_BYTES", 20 * 1024 * 1024),
        pdf_max_pages=_env_int("PDF_MAX_PAGES", 30),
        pdf_ocr_enabled=_env_bool("PDF_OCR_ENABLED", True),
        pdf_ocr_min_chars=_env_int("PDF_OCR_MIN_CHARS", 50),
        pdf_ocr_dpi=_env_int("PDF_OCR_DPI", 200),
        patent_doc_context_chars=_env_int("PATENT_DOC_CONTEXT_CHARS", 12000),
        kg_backend=(
            _env_str("KG_BACKEND", "neo4j" if _env_str("NEO4J_URI") else "memory") or "memory"
        ).lower(),
        neo4j_uri=_env_str("NEO4J_URI"),
        neo4j_user=_env_str("NEO4J_USER", _env_str("NEO4J_USERNAME", "neo4j")) or "neo4j",
        neo4j_password=_env_str("NEO4J_PASSWORD"),
        neo4j_database=_env_str("NEO4J_DATABASE"),
        kg_auto_seed=_env_bool("KG_AUTO_SEED", True),
        kg_corpus_dir=_env_str("KG_CORPUS_DIR", "./data/raw/corpus") or "./data/raw/corpus",
        kg_record_responses=_env_bool("KG_RECORD_RESPONSES", True),
        bhashini_enabled=_env_bool("BHASHINI_ENABLED", False),
        bhashini_user_id=_env_str("BHASHINI_USER_ID"),
        bhashini_api_key=_env_str("BHASHINI_API_KEY"),
        bhashini_base_url=_env_str(
            "BHASHINI_BASE_URL",
            "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline",
        )
        or "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline",
        bhashini_pipeline_id=_env_str("BHASHINI_PIPELINE_ID", "64392f96daac500b55c543cd"),
        bhashini_default_source_language=_env_str("BHASHINI_DEFAULT_SOURCE_LANGUAGE", "en") or "en",
        bhashini_default_target_language=_env_str("BHASHINI_DEFAULT_TARGET_LANGUAGE", "en") or "en",
        bhashini_asr_service=_env_str("BHASHINI_ASR_SERVICE"),
        bhashini_translation_service=_env_str("BHASHINI_TRANSLATION_SERVICE"),
        bhashini_tts_service=_env_str("BHASHINI_TTS_SERVICE"),
        bhashini_timeout=_env_float("BHASHINI_TIMEOUT", 20.0),
        audio_max_bytes=_env_int("AUDIO_MAX_BYTES", 5 * 1024 * 1024),
    )
