"""Market Feasibility — web search evidence + NIM structured assessment."""

from __future__ import annotations

from typing import Any

from config import Settings, get_settings
from graph.models import MarketFeasibilityAssessment, RetrievedSource
from graph.product_review.common import (
    botanical_context,
    coerce_scope,
    filter_ids,
    finalize_rating,
    product_document_context,
    resource_names,
    sanitize_findings,
    search_country,
    target_market,
)
from graph.prompts import MARKET_FEASIBILITY_SYSTEM
from llm.provider import get_chat_model
from llm.structured import format_sources_for_prompt, structured_invoke
from websearch.base import WebSearcher, search_many


def build_market_queries(state: dict[str, Any]) -> list[str]:
    product = (state.get("product") or "").strip()
    market = target_market(state)
    category = (state.get("product_category") or "Ayurvedic").strip()
    names = resource_names(state, limit=2)
    queries = [f"{product} {category} products market {market}"]
    for name in names:
        queries.append(f"{name} supplement brands competitors {market}")
    if names:
        queries.append(f"{names[0]} herbal products consumer demand {market}")
    return queries


def assess_market_feasibility(
    state: dict[str, Any],
    sources: list[RetrievedSource],
    *,
    llm: Any,
) -> MarketFeasibilityAssessment:
    market = target_market(state)
    if not sources:
        return MarketFeasibilityAssessment(
            summary="Insufficient market evidence: no web search results were retrieved.",
            target_market=market,
            insufficient_evidence=True,
        )

    user = "\n".join(
        [
            f"product={state.get('product') or ''}",
            f"product_category_hint={state.get('product_category') or ''}",
            f"target_market={market}",
            "Botanical normalization:",
            botanical_context(state),
            "Assess market feasibility from the sources below only. "
            "Cite evidence_source_ids for competitors, demand indicators and findings.",
            *product_document_context(state),
            "Retrieved sources:",
            format_sources_for_prompt(sources),
        ]
    )
    result = structured_invoke(
        llm, MarketFeasibilityAssessment, system=MARKET_FEASIBILITY_SYSTEM, user=user
    )
    result.target_market = result.target_market or market

    valid = {s.id for s in sources}
    sanitize_findings(result.findings, valid)
    sanitize_findings(result.demand_indicators, valid)
    for competitor in result.competitors:
        competitor.evidence_source_ids = filter_ids(competitor.evidence_source_ids, valid)
    # Uncited competitors are likely model recall, not evidence.
    result.competitors = [c for c in result.competitors if c.evidence_source_ids]

    cited = [
        i
        for group in (result.findings, result.demand_indicators, result.competitors)
        for item in group
        for i in item.evidence_source_ids
    ]
    finalize_rating(result, cited)
    return result


def market_feasibility_node(
    state: dict[str, Any],
    *,
    searcher: WebSearcher,
    settings: Settings | None = None,
    llm: Any | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    model = llm if llm is not None else get_chat_model(settings=cfg)

    sources, errors = search_many(
        searcher,
        build_market_queries(state),
        num_results=cfg.web_search_results,
        jurisdiction=target_market(state).lower(),
        legal_scope=coerce_scope(state.get("legal_scope")),
        country=search_country(state),
    )
    assessment = assess_market_feasibility(state, sources, llm=model)

    reasons: list[str] = []
    if errors:
        reasons.append("web_search_failed")
    if assessment.insufficient_evidence:
        reasons.append("missing_market_evidence")

    update: dict[str, Any] = {
        "market_sources": sources,
        "market_feasibility": assessment,
    }
    if reasons:
        update["escalation_reasons"] = reasons
    return update
