"""Environment-backed settings for AyurDisha backend."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


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

    # Confidence / escalation placeholders
    botanical_confidence_threshold: float = Field(default=0.7)
    verification_min_support_ratio: float = Field(default=0.6)
    max_verifier_retries: int = Field(default=1)


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
        botanical_confidence_threshold=_env_float(
            "BOTANICAL_CONFIDENCE_THRESHOLD", 0.7
        ),
        verification_min_support_ratio=_env_float(
            "VERIFICATION_MIN_SUPPORT_RATIO", 0.6
        ),
        max_verifier_retries=_env_int("MAX_VERIFIER_RETRIES", 1),
    )
