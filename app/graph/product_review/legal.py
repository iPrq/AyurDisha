"""Legal Compliance — regulation corpus retrieval + (regulator-scoped) web search."""

from __future__ import annotations

from typing import Any

from config import Settings, get_settings
from graph.models import LegalComplianceAssessment, LegalScope, RetrievedSource
from graph.product_review.common import (
    botanical_context,
    coerce_scope,
    finalize_rating,
    invoke_assessment,
    merge_sources,
    product_document_context,
    sanitize_findings,
    target_market,
)
from graph.prompts import LEGAL_COMPLIANCE_SYSTEM, legal_scope_instruction
from llm.provider import get_chat_model
from llm.structured import format_sources_for_prompt
from retrieval.base import LegalRetriever
from retrieval.mock import get_mock_retriever
from websearch.base import NO_COUNTRY_BIAS, WebSearcher, search_many
from websearch.domains import INDIA_REGULATOR_DOMAINS, INTERNATIONAL_REGULATOR_DOMAINS

REGULATION_SOURCE_TYPES = ["regulation"]


def build_legal_query(state: dict[str, Any]) -> str:
    category = (state.get("product_category") or "Ayurvedic").strip()
    parts = [
        category,
        state.get("product") or "",
        *(state.get("ingredients") or []),
        "licence regulation requirements",
    ]
    return " ".join(p for p in parts if p).strip()


def assess_legal_compliance(
    state: dict[str, Any],
    sources: list[RetrievedSource],
    *,
    llm: Any,
) -> LegalComplianceAssessment:
    jurisdiction = state.get("jurisdiction") or "india"
    scope = coerce_scope(state.get("legal_scope"))

    if scope == LegalScope.INTERNATIONAL and not any(
        s.legal_scope == LegalScope.INTERNATIONAL for s in sources
    ):
        return LegalComplianceAssessment(
            summary=(
                "Insufficient international regulatory evidence. "
                "Human review required — foreign law not invented."
            ),
            insufficient_evidence=True,
            legal_scope=scope,
        )
    if not sources:
        return LegalComplianceAssessment(
            summary="Insufficient regulatory evidence: no sources retrieved.",
            insufficient_evidence=True,
            legal_scope=scope,
        )

    user = "\n".join(
        [
            legal_scope_instruction(scope, jurisdiction),
            f"product={state.get('product') or ''}",
            f"product_category_hint={state.get('product_category') or ''}",
            f"target_market={target_market(state)}",
            "Botanical normalization:",
            botanical_context(state),
            "Identify regulatory category, requirements and restrictions from sources only.",
            *product_document_context(state),
            "Retrieved sources:",
            format_sources_for_prompt(sources),
        ]
    )
    result = invoke_assessment(
        llm, LegalComplianceAssessment, system=LEGAL_COMPLIANCE_SYSTEM, user=user
    )
    result.legal_scope = scope

    valid = {s.id for s in sources}
    sanitize_findings(result.requirements, valid)
    sanitize_findings(result.restrictions, valid)
    cited = [
        i
        for group in (result.requirements, result.restrictions)
        for item in group
        for i in item.evidence_source_ids
    ]
    finalize_rating(result, cited)
    return result


def legal_compliance_node(
    state: dict[str, Any],
    *,
    retriever: LegalRetriever | None = None,
    searcher: WebSearcher,
    settings: Settings | None = None,
    llm: Any | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    model = llm if llm is not None else get_chat_model(settings=cfg)
    client = retriever or get_mock_retriever()

    jurisdiction = state.get("jurisdiction") or "india"
    scope = coerce_scope(state.get("legal_scope"))
    query = build_legal_query(state)

    corpus_hits = client.retrieve(
        query,
        jurisdiction=jurisdiction,
        legal_scope=scope,
        top_k=6,
        source_types=REGULATION_SOURCE_TYPES,
    )

    if scope == LegalScope.INTERNATIONAL:
        market = target_market(state)
        # A named target market may have a regulator outside the curated list.
        domains = None if state.get("target_market") else INTERNATIONAL_REGULATOR_DOMAINS
        web_hits, errors = search_many(
            searcher,
            [f"{query} {market}"],
            num_results=cfg.web_search_results,
            include_domains=domains,
            jurisdiction=market.lower(),
            legal_scope=LegalScope.INTERNATIONAL,
            country=NO_COUNTRY_BIAS,
        )
    else:
        domains = INDIA_REGULATOR_DOMAINS if jurisdiction.lower() == "india" else None
        web_hits, errors = search_many(
            searcher,
            [query],
            num_results=cfg.web_search_results,
            include_domains=domains,
            jurisdiction=jurisdiction,
            legal_scope=LegalScope.DOMESTIC,
        )

    sources = merge_sources(corpus_hits, web_hits)
    assessment = assess_legal_compliance(state, sources, llm=model)

    reasons: list[str] = []
    if errors:
        reasons.append("web_search_failed")
    if assessment.insufficient_evidence:
        reasons.append(
            "insufficient_international_evidence"
            if scope == LegalScope.INTERNATIONAL
            else "missing_regulatory_evidence"
        )

    update: dict[str, Any] = {
        "legal_sources": sources,
        "legal_compliance": assessment,
    }
    if reasons:
        update["escalation_reasons"] = reasons
    return update
