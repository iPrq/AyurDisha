"""Fixture-backed mock retrieval (not connected to Qdrant)."""

from __future__ import annotations

from graph.models import LegalScope, RetrievedSource
from retrieval.base import filter_sources


# All entries are TEST FIXTURES — not government or live corpus data.
_FIXTURES: list[RetrievedSource] = [
    RetrievedSource(
        id="fixture-in-s3d",
        title="[TEST FIXTURE] Indian Patents Act — Section 3(d) summary",
        text=(
            "[TEST FIXTURE — NOT OFFICIAL TEXT] Section 3(d) concerns the mere discovery "
            "of a new form of a known substance which does not result in the enhancement "
            "of the known efficacy of that substance, and the mere discovery of any new "
            "property or new use for a known substance."
        ),
        section="3(d)",
        source_type="statute_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.92,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    ),
    RetrievedSource(
        id="fixture-in-s3e",
        title="[TEST FIXTURE] Indian Patents Act — Section 3(e) summary",
        text=(
            "[TEST FIXTURE — NOT OFFICIAL TEXT] Section 3(e) excludes a substance obtained "
            "by a mere admixture resulting only in the aggregation of the properties of "
            "the components thereof, or a process for producing such substance."
        ),
        section="3(e)",
        source_type="statute_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.90,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    ),
    RetrievedSource(
        id="fixture-in-s3p",
        title="[TEST FIXTURE] Indian Patents Act — Section 3(p) summary",
        text=(
            "[TEST FIXTURE — NOT OFFICIAL TEXT] Section 3(p) excludes an invention which, "
            "in effect, is traditional knowledge or which is an aggregation or duplication "
            "of known properties of traditionally known component or components."
        ),
        section="3(p)",
        source_type="statute_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.91,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    ),
    RetrievedSource(
        id="fixture-in-prior-art",
        title="[TEST FIXTURE] Sample prior-art note — Withania formulations",
        text=(
            "[TEST FIXTURE] Prior disclosures discuss Withania somnifera root extracts "
            "used in traditional preparations. This fixture is for retrieval testing only."
        ),
        section=None,
        source_type="prior_art_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.75,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    ),
    RetrievedSource(
        id="fixture-in-ip-routes",
        title="[TEST FIXTURE] Domestic IP pathway overview",
        text=(
            "[TEST FIXTURE] Depending on subject matter, applicants may consider patent, "
            "trademark, design, or trade secret pathways. This is decision-support fixture "
            "text only — not legal advice."
        ),
        section=None,
        source_type="guidance_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.70,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    ),
    RetrievedSource(
        id="fixture-intl-trips",
        title="[TEST FIXTURE] Comparative IP — TRIPS-oriented note",
        text=(
            "[TEST FIXTURE — NOT OFFICIAL TEXT] Comparative international IP materials may "
            "discuss patentable subject matter standards under TRIPS-oriented frameworks. "
            "This fixture exists only to test legal_scope=international filtering."
        ),
        section=None,
        source_type="comparative_ip_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.80,
        jurisdiction="wipo",
        legal_scope=LegalScope.INTERNATIONAL,
        is_fixture=True,
    ),
    RetrievedSource(
        id="fixture-intl-epo-note",
        title="[TEST FIXTURE] Comparative IP — EPO-style subject-matter note",
        text=(
            "[TEST FIXTURE — NOT OFFICIAL TEXT] Some jurisdictions apply distinct exclusions "
            "for plant varieties, methods of treatment, or traditional knowledge analogues. "
            "Cite only retrieved comparative fixtures; never invent foreign statutes."
        ),
        section=None,
        source_type="comparative_ip_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.72,
        jurisdiction="epo",
        legal_scope=LegalScope.INTERNATIONAL,
        is_fixture=True,
    ),
]


def _score_query(source: RetrievedSource, query: str) -> float:
    """Simple lexical boost on top of fixture retrieval_score."""
    q = query.lower()
    blob = f"{source.title} {source.text} {source.section or ''}".lower()
    bonus = 0.0
    for token in q.split():
        if len(token) > 2 and token in blob:
            bonus += 0.02
    return min(1.0, source.retrieval_score + bonus)


class MockLegalRetriever:
    """In-memory retriever with jurisdiction / legal_scope filters."""

    def __init__(self, corpus: list[RetrievedSource] | None = None) -> None:
        self._corpus = list(corpus) if corpus is not None else list(_FIXTURES)

    def retrieve(
        self,
        query: str,
        *,
        jurisdiction: str = "india",
        legal_scope: LegalScope | str = LegalScope.DOMESTIC,
        top_k: int = 8,
    ) -> list[RetrievedSource]:
        filtered = filter_sources(
            self._corpus,
            jurisdiction=jurisdiction,
            legal_scope=legal_scope,
        )
        ranked = sorted(
            filtered,
            key=lambda s: _score_query(s, query or ""),
            reverse=True,
        )
        return ranked[:top_k]


def get_mock_retriever() -> MockLegalRetriever:
    return MockLegalRetriever()


def get_fixture_corpus() -> list[RetrievedSource]:
    """Expose fixture list for tests."""
    return list(_FIXTURES)
