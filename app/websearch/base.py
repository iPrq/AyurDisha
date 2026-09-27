"""Web search protocol + conversion of hits into citable RetrievedSource evidence."""

from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol, runtime_checkable
from urllib.parse import urlparse

from pydantic import BaseModel

from graph.models import LegalScope, RetrievedSource

logger = logging.getLogger(__name__)


class WebSearchError(RuntimeError):
    """A provider call failed (network, quota, bad response)."""


class WebSearchConfigError(RuntimeError):
    """WEB_SEARCH_BACKEND is unknown or its API key is missing."""


class WebSearchResult(BaseModel):
    title: str
    url: str | None = None
    snippet: str = ""
    published_date: str | None = None
    rank: int = 1
    is_fixture: bool = False


@runtime_checkable
class WebSearcher(Protocol):
    def search(
        self,
        query: str,
        *,
        num_results: int = 5,
        include_domains: list[str] | None = None,
    ) -> list[WebSearchResult]:
        ...


class NullWebSearcher:
    """WEB_SEARCH_BACKEND=none — web evidence disabled; nodes escalate on missing evidence."""

    def search(
        self,
        query: str,
        *,
        num_results: int = 5,
        include_domains: list[str] | None = None,
    ) -> list[WebSearchResult]:
        return []


def site_filter(include_domains: list[str] | None) -> str:
    if not include_domains:
        return ""
    return " (" + " OR ".join(f"site:{d}" for d in include_domains) + ")"


def _source_id(result: WebSearchResult) -> str:
    key = result.url or f"{result.title}|{result.snippet}"
    return "web_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def to_retrieved_source(
    result: WebSearchResult,
    *,
    jurisdiction: str | None = None,
    legal_scope: LegalScope | None = None,
) -> RetrievedSource:
    domain = urlparse(result.url).netloc if result.url else None
    return RetrievedSource(
        id=_source_id(result),
        title=result.title,
        text=result.snippet,
        section=domain,
        source_type="web_fixture" if result.is_fixture else "web",
        source_url=result.url,
        effective_date=result.published_date,
        retrieval_score=max(0.0, 1.0 - 0.05 * (result.rank - 1)),
        jurisdiction=jurisdiction,
        legal_scope=legal_scope,
        is_fixture=result.is_fixture,
    )


def search_many(
    searcher: WebSearcher,
    queries: list[str],
    *,
    num_results: int = 5,
    include_domains: list[str] | None = None,
    jurisdiction: str | None = None,
    legal_scope: LegalScope | None = None,
) -> tuple[list[RetrievedSource], list[str]]:
    """Run queries concurrently; return de-duplicated sources and per-query errors."""
    queries = [q for q in dict.fromkeys(q.strip() for q in queries) if q]
    if not queries:
        return [], []

    def _one(query: str) -> list[WebSearchResult]:
        return searcher.search(
            query, num_results=num_results, include_domains=include_domains
        )

    sources: dict[str, RetrievedSource] = {}
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=min(4, len(queries))) as pool:
        futures = [(q, pool.submit(_one, q)) for q in queries]
        for query, future in futures:
            try:
                hits = future.result()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Web search failed for %r: %s", query, exc)
                errors.append(f"{query}: {exc}")
                continue
            for hit in hits:
                src = to_retrieved_source(
                    hit, jurisdiction=jurisdiction, legal_scope=legal_scope
                )
                if src.id not in sources:
                    sources[src.id] = src
    return list(sources.values()), errors
