"""Web search layer: mock, source conversion, provider parsing, factory config (offline)."""

from __future__ import annotations

import httpx
import pytest

from config import Settings
from websearch.base import (
    NullWebSearcher,
    WebSearchError,
    WebSearchResult,
    search_many,
    site_filter,
    to_retrieved_source,
)
from websearch.factory import get_web_searcher
from websearch.mock import MockWebSearcher
from websearch.providers import (
    GoogleCSEWebSearcher,
    SerperWebSearcher,
    TavilyWebSearcher,
)


def test_mock_search_matches_keywords_and_has_no_urls():
    hits = MockWebSearcher().search("ashwagandha brands competitors india")
    assert hits
    assert all(h.is_fixture and h.url is None for h in hits)


def test_to_retrieved_source_is_stable_and_citable():
    res = WebSearchResult(title="T", url="https://example.org/a", snippet="S", rank=3)
    a = to_retrieved_source(res)
    b = to_retrieved_source(res)
    assert a.id == b.id and a.id.startswith("web_")
    assert a.source_type == "web"
    assert a.source_url == "https://example.org/a"
    assert a.section == "example.org"
    assert a.retrieval_score == pytest.approx(0.9)


def test_search_many_dedupes_and_collects_errors():
    class Flaky:
        def search(self, query, *, num_results=5, include_domains=None):
            if "boom" in query:
                raise WebSearchError("quota")
            return [WebSearchResult(title="same", url="https://x.org", snippet="s")]

    sources, errors = search_many(Flaky(), ["one", "two", "boom", "one"])
    assert len(sources) == 1
    assert len(errors) == 1 and "quota" in errors[0]


def test_null_searcher_returns_nothing():
    assert NullWebSearcher().search("anything") == []


def test_site_filter():
    assert site_filter(["a.gov.in", "b.gov.in"]) == " (site:a.gov.in OR site:b.gov.in)"
    assert site_filter(None) == ""


def _fake_response(payload, status=200):
    return httpx.Response(status, json=payload, request=httpx.Request("GET", "https://t"))


def test_serper_parsing(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return _fake_response(
            {"organic": [{"title": "A", "link": "https://a.in", "snippet": "sa", "position": 1}]}
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    hits = SerperWebSearcher("k").search("q", include_domains=["ayush.gov.in"])
    assert hits[0].url == "https://a.in"
    assert "site:ayush.gov.in" in captured["json"]["q"]
    assert captured["headers"]["X-API-KEY"] == "k"


def test_google_cse_parsing_caps_num(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured.update(kwargs)
        return _fake_response({"items": [{"title": "B", "link": "https://b.in", "snippet": "sb"}]})

    monkeypatch.setattr(httpx, "get", fake_get)
    hits = GoogleCSEWebSearcher("k", "cx").search("q", num_results=50)
    assert hits[0].title == "B"
    assert captured["params"]["num"] == 10


def test_tavily_parsing_and_http_error(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **kw: _fake_response(
            {"results": [{"title": "C", "url": "https://c.in", "content": "sc"}]}
        ),
    )
    assert TavilyWebSearcher("k").search("q")[0].snippet == "sc"

    monkeypatch.setattr(httpx, "post", lambda url, **kw: _fake_response({}, status=429))
    with pytest.raises(WebSearchError):
        TavilyWebSearcher("k").search("q")


def test_factory_backends():
    assert isinstance(get_web_searcher(Settings(web_search_backend="mock")), MockWebSearcher)
    assert isinstance(get_web_searcher(Settings(web_search_backend="none")), NullWebSearcher)
    assert isinstance(
        get_web_searcher(Settings(web_search_backend="serper", serper_api_key="k")),
        SerperWebSearcher,
    )


@pytest.mark.parametrize(
    "settings",
    [
        Settings(web_search_backend="serper"),
        Settings(web_search_backend="google_cse", google_cse_api_key="k"),
        Settings(web_search_backend="tavily"),
        Settings(web_search_backend="bing"),
    ],
)
def test_factory_never_falls_back_to_mock(settings):
    with pytest.raises(RuntimeError):
        get_web_searcher(settings)
