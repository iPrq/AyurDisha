"""Hybrid retrieval protocol and jurisdiction / legal_scope filters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from graph.models import LegalScope, RetrievedSource


def coerce_legal_scope(value: LegalScope | str | None) -> LegalScope | None:
    if value is None:
        return None
    if isinstance(value, LegalScope):
        return value
    return LegalScope(str(value).lower())


def matches_scope_filters(
    source: RetrievedSource,
    *,
    jurisdiction: str | None = None,
    legal_scope: LegalScope | str | None = None,
) -> bool:
    """Return True if ``source`` should be included for the given switch.

    domestic:
      - source.legal_scope is domestic (or unset treated as domestic)
      - if jurisdiction is set, source.jurisdiction must match (case-insensitive)
    international:
      - source.legal_scope is international only (never invent by including domestic
        statutes as if they were comparative law)
    """
    scope = coerce_legal_scope(legal_scope) or LegalScope.DOMESTIC
    src_scope = coerce_legal_scope(source.legal_scope) or LegalScope.DOMESTIC

    if scope == LegalScope.INTERNATIONAL:
        return src_scope == LegalScope.INTERNATIONAL

    # domestic
    if src_scope != LegalScope.DOMESTIC:
        return False
    if jurisdiction:
        src_j = (source.jurisdiction or "").strip().lower()
        if src_j and src_j != jurisdiction.strip().lower():
            return False
    return True


def filter_sources(
    sources: list[RetrievedSource],
    *,
    jurisdiction: str | None = None,
    legal_scope: LegalScope | str | None = None,
) -> list[RetrievedSource]:
    """Filter a corpus by jurisdiction / legal_scope switch."""
    return [
        s
        for s in sources
        if matches_scope_filters(s, jurisdiction=jurisdiction, legal_scope=legal_scope)
    ]


@runtime_checkable
class LegalRetriever(Protocol):
    """Retrieve legal / patent sources (mock fixtures or Qdrant + BM25 hybrid).

    ``source_types`` optionally restricts results (e.g. ["statute", "guideline"]).
    """

    def retrieve(
        self,
        query: str,
        *,
        jurisdiction: str = "india",
        legal_scope: LegalScope | str = LegalScope.DOMESTIC,
        top_k: int = 8,
        source_types: list[str] | None = None,
    ) -> list[RetrievedSource]:
        ...
