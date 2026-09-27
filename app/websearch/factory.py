"""WEB_SEARCH_BACKEND=mock|serper|google_cse|tavily|none. Never silently falls back to mock."""

from __future__ import annotations

import logging

from config import Settings, get_settings
from websearch.base import NullWebSearcher, WebSearchConfigError, WebSearcher
from websearch.mock import MockWebSearcher

logger = logging.getLogger(__name__)


def _require(value: str | None, env_name: str, backend: str) -> str:
    if not value:
        raise WebSearchConfigError(
            f"WEB_SEARCH_BACKEND={backend} requires {env_name} to be set."
        )
    return value


def get_web_searcher(settings: Settings | None = None) -> WebSearcher:
    cfg = settings or get_settings()
    backend = (cfg.web_search_backend or "").strip().lower()
    logger.info("Web search backend=%s", backend)

    if backend == "mock":
        return MockWebSearcher()
    if backend == "none":
        return NullWebSearcher()
    if backend == "serper":
        from websearch.providers import SerperWebSearcher

        return SerperWebSearcher(
            _require(cfg.serper_api_key, "SERPER_API_KEY", backend),
            country=cfg.web_search_country,
            timeout=cfg.web_search_timeout,
        )
    if backend == "google_cse":
        from websearch.providers import GoogleCSEWebSearcher

        return GoogleCSEWebSearcher(
            _require(cfg.google_cse_api_key, "GOOGLE_CSE_API_KEY", backend),
            _require(cfg.google_cse_id, "GOOGLE_CSE_ID", backend),
            country=cfg.web_search_country,
            timeout=cfg.web_search_timeout,
        )
    if backend == "tavily":
        from websearch.providers import TavilyWebSearcher

        return TavilyWebSearcher(
            _require(cfg.tavily_api_key, "TAVILY_API_KEY", backend),
            timeout=cfg.web_search_timeout,
        )
    raise WebSearchConfigError(
        f"Unsupported WEB_SEARCH_BACKEND={cfg.web_search_backend!r}; "
        "expected mock, serper, google_cse, tavily, or none."
    )
