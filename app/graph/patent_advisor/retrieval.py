"""Legal / patent retrieval node for Patent Advisor."""

from __future__ import annotations

from typing import Any

from config import Settings, get_settings
from graph.models import SUPPORTED_SECTION3_CLAUSES, LegalScope, RetrievedSource
from graph.state import PatentAdvisorState
from retrieval.base import LegalRetriever
from retrieval.mock import get_mock_retriever
from websearch.base import NO_COUNTRY_BIAS, WebSearcher, search_many
from websearch.domains import INTERNATIONAL_IP_DOMAINS

# Keeps product-regulation / ABS chunks out of patent reasoning.
PATENT_SOURCE_TYPES = [
    "statute",
    "guideline",
    "patent",
    "comparative_ip",
    "prior_art",
    "case_law",
    "guidance",
]


def _build_query(state: PatentAdvisorState) -> str:
    parts: list[str] = []
    if state.get("botanical_name"):
        parts.append(str(state["botanical_name"]))
    if state.get("botanical_input"):
        parts.append(str(state["botanical_input"]))
    if state.get("product"):
        parts.append(str(state["product"]))
    ingredients = state.get("ingredients") or []
    parts.extend(str(i) for i in ingredients)
    scope = state.get("legal_scope") or "domestic"
    if str(scope).lower() == "international":
        parts.append("comparative international IP patentable subject matter")
    else:
        parts.append("Section 3 patent traditional knowledge")
    return " ".join(parts)


SECTION3_STATUTE_SOURCE_TYPES = ["statute"]
# Section labels kept from the focused statute retrieval: the preamble ("3") and
# the supported clauses. Anything else (other sections, other clauses) is dropped.
_SECTION3_SECTION_LABELS = frozenset({"3", *SUPPORTED_SECTION3_CLAUSES})


def _build_section3_statute_query(state: PatentAdvisorState) -> str:
    """Query naming every supported clause ref so BM25 can match each clause chunk."""
    parts: list[str] = ["Section 3", *SUPPORTED_SECTION3_CLAUSES]
    for key in ("botanical_name", "product"):
        if state.get(key):
            parts.append(str(state[key]))
    return " ".join(parts)


def _scope_value(legal_scope: LegalScope | str) -> str:
    return (
        legal_scope.value if isinstance(legal_scope, LegalScope) else str(legal_scope)
    ).lower()


def _wants_section3_statutes(jurisdiction: str, legal_scope: LegalScope | str) -> bool:
    return (
        _scope_value(legal_scope) == LegalScope.DOMESTIC.value
        and jurisdiction.strip().lower() == "india"
    )


def _merge_sources(
    primary: list[RetrievedSource], extra: list[RetrievedSource]
) -> list[RetrievedSource]:
    """Keep ``primary`` order; append unseen ``extra`` sources (dedupe by id)."""
    seen = {s.id for s in primary}
    merged = list(primary)
    for s in extra:
        if s.id not in seen:
            seen.add(s.id)
            merged.append(s)
    return merged


def _build_ip_web_query(state: PatentAdvisorState) -> str:
    parts = [
        str(state.get("botanical_name") or state.get("product") or ""),
        *(str(i) for i in (state.get("ingredients") or [])[:3]),
        "herbal composition patent",
    ]
    return " ".join(p for p in parts if p)


def legal_patent_retrieval_node(
    state: PatentAdvisorState,
    *,
    retriever: LegalRetriever | None = None,
    searcher: WebSearcher | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    client = retriever or get_mock_retriever()
    jurisdiction = state.get("jurisdiction") or "india"
    legal_scope = state.get("legal_scope") or LegalScope.DOMESTIC
    query = _build_query(state)
    sources = client.retrieve(
        query,
        jurisdiction=jurisdiction,
        legal_scope=legal_scope,
        source_types=PATENT_SOURCE_TYPES,
    )

    # The international corpus is thin; supplement it with IP-office web evidence.
    web_errors: list[str] = []
    if searcher is not None and _scope_value(legal_scope) == LegalScope.INTERNATIONAL.value:
        cfg = settings or get_settings()
        web_hits, web_errors = search_many(
            searcher,
            [_build_ip_web_query(state)],
            num_results=cfg.web_search_results,
            include_domains=INTERNATIONAL_IP_DOMAINS,
            legal_scope=LegalScope.INTERNATIONAL,
            country=NO_COUNTRY_BIAS,
        )
        sources = _merge_sources(sources, web_hits)

    # Focused statute retrieval so Section 3 reliably sees the clause chunks.
    # Same retriever (Qdrant + BM25 + RRF [+ rerank]) and filters; domestic India only.
    if _wants_section3_statutes(jurisdiction, legal_scope):
        cfg = settings or get_settings()
        # Request every fused candidate (dense + BM25) so rank fusion cannot cut a
        # clause found by only one of the two searches before the Section 3 filter.
        top_k = max(cfg.section3_statute_top_k, cfg.dense_candidates + cfg.bm25_candidates)
        statute_sources = client.retrieve(
            _build_section3_statute_query(state),
            jurisdiction=jurisdiction,
            legal_scope=legal_scope,
            top_k=top_k,
            source_types=SECTION3_STATUTE_SOURCE_TYPES,
        )
        # Rank alone can drop long clauses (e.g. one with an Explanation) behind
        # unrelated sections, so request a wide candidate set and keep Section 3 only.
        statute_sources = [
            s
            for s in statute_sources
            if (s.section or "").strip().lower() in _SECTION3_SECTION_LABELS
        ]
        sources = _merge_sources(sources, statute_sources)

    update: dict[str, Any] = {
        "retrieved_sources": sources,
        "retrieval_insufficient": len(sources) == 0,
    }

    reasons = list(state.get("escalation_reasons") or [])
    if web_errors and "web_search_failed" not in reasons:
        reasons.append("web_search_failed")
        update["escalation_reasons"] = reasons
    if len(sources) == 0:
        if _scope_value(legal_scope) == LegalScope.INTERNATIONAL.value:
            if "insufficient_international_evidence" not in reasons:
                reasons.append("insufficient_international_evidence")
            update["verification_status"] = "HUMAN_REVIEW_REQUIRED"
        else:
            if "missing_evidence" not in reasons:
                reasons.append("missing_evidence")
        update["escalation_reasons"] = reasons

    return update


def make_retrieval_node(
    *,
    retriever: LegalRetriever | None = None,
    searcher: WebSearcher | None = None,
    settings: Settings | None = None,
):
    def _node(state: PatentAdvisorState) -> dict[str, Any]:
        return legal_patent_retrieval_node(
            state, retriever=retriever, searcher=searcher, settings=settings
        )

    return _node
