"""Fixture web search (offline). Results carry no URLs — never fabricate links."""

from __future__ import annotations

import re

from websearch.base import WebSearchResult

# (keywords, result). A fixture matches when any keyword appears in the query.
_FIXTURES: list[tuple[set[str], WebSearchResult]] = [
    (
        {"market", "brands", "competitors", "demand"},
        WebSearchResult(
            title="[TEST FIXTURE] Herbal supplement market overview",
            snippet=(
                "[TEST FIXTURE — NOT REAL MARKET DATA] Several consumer brands sell "
                "single-herb Ayurvedic capsules and powders through pharmacies and "
                "e-commerce channels. This fixture exists only for offline testing."
            ),
            is_fixture=True,
        ),
    ),
    (
        {"market", "brands", "competitors"},
        WebSearchResult(
            title="[TEST FIXTURE] Competitor listing — Ayurvedic capsules",
            snippet=(
                "[TEST FIXTURE — NOT REAL MARKET DATA] Example listing of existing "
                "Ayurvedic proprietary products in the same category."
            ),
            rank=2,
            is_fixture=True,
        ),
    ),
    (
        {"cultivation", "availability", "supply"},
        WebSearchResult(
            title="[TEST FIXTURE] Medicinal plant cultivation note",
            snippet=(
                "[TEST FIXTURE — NOT REAL AGRONOMIC DATA] The plant is reported as "
                "cultivated in several Indian states; supply depends on seasonal harvest."
            ),
            is_fixture=True,
        ),
    ),
    (
        {"conservation", "iucn", "wild", "sustainability"},
        WebSearchResult(
            title="[TEST FIXTURE] Conservation and wild-harvest note",
            snippet=(
                "[TEST FIXTURE — NOT REAL CONSERVATION DATA] Sustainability of wild "
                "collection should be checked against current conservation assessments."
            ),
            rank=2,
            is_fixture=True,
        ),
    ),
    (
        {"licence", "license", "regulation", "regulatory"},
        WebSearchResult(
            title="[TEST FIXTURE] Regulator guidance page",
            snippet=(
                "[TEST FIXTURE — NOT OFFICIAL TEXT] Manufacturers of Ayurvedic "
                "medicines require a manufacturing licence from the State Licensing Authority."
            ),
            is_fixture=True,
        ),
    ),
]


class MockWebSearcher:
    def __init__(
        self, fixtures: list[tuple[set[str], WebSearchResult]] | None = None
    ) -> None:
        self._fixtures = list(fixtures) if fixtures is not None else list(_FIXTURES)
        self.queries: list[str] = []

    def search(
        self,
        query: str,
        *,
        num_results: int = 5,
        include_domains: list[str] | None = None,
        country: str | None = None,
    ) -> list[WebSearchResult]:
        self.queries.append(query)
        tokens = set(re.findall(r"[a-z]+", query.lower()))
        hits = [res for keys, res in self._fixtures if keys & tokens]
        return hits[:num_results]
