"""Language provider factory — BHASHINI when fully configured, otherwise the fallback provider."""

from __future__ import annotations

from config import Settings, get_settings
from language.base import LanguageProvider
from language.fallback import FallbackLanguageProvider

_provider: LanguageProvider | None = None


def build_language_provider(settings: Settings | None = None) -> LanguageProvider:
    cfg = settings or get_settings()
    if not cfg.bhashini_enabled:
        return FallbackLanguageProvider("BHASHINI is disabled (BHASHINI_ENABLED is not set).")
    if not (cfg.bhashini_user_id and cfg.bhashini_api_key):
        return FallbackLanguageProvider(
            "BHASHINI is enabled but BHASHINI_USER_ID / BHASHINI_API_KEY are missing."
        )
    from language.bhashini import BhashiniLanguageProvider

    return BhashiniLanguageProvider(cfg)


def get_language_provider(settings: Settings | None = None) -> LanguageProvider:
    global _provider
    if _provider is None:
        _provider = build_language_provider(settings)
    return _provider


def set_language_provider(provider: LanguageProvider | None) -> None:
    """Test hook."""
    global _provider
    _provider = provider
