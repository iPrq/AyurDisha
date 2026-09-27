"""Live web search providers: Serper (Google SERP), Google Programmable Search, Tavily."""

from __future__ import annotations

from typing import Any

import httpx

from websearch.base import WebSearchError, WebSearchResult, site_filter


def _get_json(response: httpx.Response, provider: str) -> dict[str, Any]:
    if response.status_code >= 400:
        raise WebSearchError(
            f"{provider} HTTP {response.status_code}: {response.text[:200]}"
        )
    try:
        return response.json()
    except ValueError as exc:
        raise WebSearchError(f"{provider} returned non-JSON response") from exc


class SerperWebSearcher:
    """Google results via https://serper.dev."""

    endpoint = "https://google.serper.dev/search"

    def __init__(self, api_key: str, *, country: str = "in", timeout: float = 15.0) -> None:
        self._api_key = api_key
        self._country = country
        self._timeout = timeout

    def search(
        self,
        query: str,
        *,
        num_results: int = 5,
        include_domains: list[str] | None = None,
    ) -> list[WebSearchResult]:
        try:
            resp = httpx.post(
                self.endpoint,
                headers={"X-API-KEY": self._api_key, "Content-Type": "application/json"},
                json={
                    "q": query + site_filter(include_domains),
                    "num": num_results,
                    "gl": self._country,
                },
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise WebSearchError(f"Serper request failed: {exc}") from exc
        data = _get_json(resp, "Serper")
        return [
            WebSearchResult(
                title=item.get("title") or "",
                url=item.get("link"),
                snippet=item.get("snippet") or "",
                published_date=item.get("date"),
                rank=int(item.get("position") or idx),
            )
            for idx, item in enumerate(data.get("organic") or [], start=1)
            if item.get("link")
        ][:num_results]


class GoogleCSEWebSearcher:
    """Google Programmable Search Engine (Custom Search JSON API)."""

    endpoint = "https://www.googleapis.com/customsearch/v1"

    def __init__(
        self,
        api_key: str,
        cse_id: str,
        *,
        country: str = "in",
        timeout: float = 15.0,
    ) -> None:
        self._api_key = api_key
        self._cse_id = cse_id
        self._country = country
        self._timeout = timeout

    def search(
        self,
        query: str,
        *,
        num_results: int = 5,
        include_domains: list[str] | None = None,
    ) -> list[WebSearchResult]:
        try:
            resp = httpx.get(
                self.endpoint,
                params={
                    "key": self._api_key,
                    "cx": self._cse_id,
                    "q": query + site_filter(include_domains),
                    # The API rejects num > 10.
                    "num": max(1, min(10, num_results)),
                    "gl": self._country,
                },
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise WebSearchError(f"Google CSE request failed: {exc}") from exc
        data = _get_json(resp, "Google CSE")
        return [
            WebSearchResult(
                title=item.get("title") or "",
                url=item.get("link"),
                snippet=item.get("snippet") or "",
                rank=idx,
            )
            for idx, item in enumerate(data.get("items") or [], start=1)
            if item.get("link")
        ][:num_results]


class TavilyWebSearcher:
    """Tavily search API (LLM-oriented; returns content extracts)."""

    endpoint = "https://api.tavily.com/search"

    def __init__(self, api_key: str, *, timeout: float = 15.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def search(
        self,
        query: str,
        *,
        num_results: int = 5,
        include_domains: list[str] | None = None,
    ) -> list[WebSearchResult]:
        payload: dict[str, Any] = {
            "query": query,
            "max_results": num_results,
            "search_depth": "basic",
        }
        if include_domains:
            payload["include_domains"] = include_domains
        try:
            resp = httpx.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise WebSearchError(f"Tavily request failed: {exc}") from exc
        data = _get_json(resp, "Tavily")
        return [
            WebSearchResult(
                title=item.get("title") or "",
                url=item.get("url"),
                snippet=item.get("content") or "",
                published_date=item.get("published_date"),
                rank=idx,
            )
            for idx, item in enumerate(data.get("results") or [], start=1)
            if item.get("url")
        ][:num_results]
