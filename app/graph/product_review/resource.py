"""Resource Accessibility — per-botanical availability / cultivation / sustainability."""

from __future__ import annotations

from typing import Any

from config import Settings, get_settings
from graph.models import ResourceAccessibilityAssessment, RetrievedSource
from graph.product_review.common import (
    botanical_context,
    filter_ids,
    finalize_rating,
    product_document_context,
    resource_names,
    sanitize_findings,
)
from graph.prompts import RESOURCE_ACCESSIBILITY_SYSTEM
from llm.provider import get_chat_model
from llm.structured import format_sources_for_prompt, structured_invoke
from websearch.base import WebSearcher, search_many


def build_resource_queries(state: dict[str, Any], limit: int) -> list[str]:
    region = (state.get("jurisdiction") or "india").strip()
    queries: list[str] = []
    for name in resource_names(state, limit=limit):
        queries.append(f"{name} cultivation availability supply {region}")
        queries.append(f"{name} conservation status wild harvest sustainability")
    return queries


def assess_resource_accessibility(
    state: dict[str, Any],
    sources: list[RetrievedSource],
    *,
    llm: Any,
) -> ResourceAccessibilityAssessment:
    if not sources:
        return ResourceAccessibilityAssessment(
            summary="Insufficient resource evidence: no sources were retrieved.",
            insufficient_evidence=True,
        )

    user = "\n".join(
        [
            f"product={state.get('product') or ''}",
            f"sourcing_region={state.get('jurisdiction') or 'india'}",
            "Required medicinal plants (botanical normalization):",
            botanical_context(state),
            "Assess availability, cultivation/supply, geography and sustainability per plant "
            "from the sources below only.",
            *product_document_context(state),
            "Retrieved sources:",
            format_sources_for_prompt(sources),
        ]
    )
    result = structured_invoke(
        llm,
        ResourceAccessibilityAssessment,
        system=RESOURCE_ACCESSIBILITY_SYSTEM,
        user=user,
    )

    valid = {s.id for s in sources}
    sanitize_findings(result.findings, valid)
    for resource in result.resources:
        resource.evidence_source_ids = filter_ids(resource.evidence_source_ids, valid)
    cited = [
        i
        for group in (result.findings, result.resources)
        for item in group
        for i in item.evidence_source_ids
    ]
    finalize_rating(result, cited)
    return result


def resource_accessibility_node(
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
        build_resource_queries(state, cfg.product_review_max_resources),
        num_results=cfg.web_search_results,
        jurisdiction=(state.get("jurisdiction") or "india").lower(),
    )
    assessment = assess_resource_accessibility(state, sources, llm=model)

    reasons: list[str] = []
    if errors:
        reasons.append("web_search_failed")
    if assessment.insufficient_evidence:
        reasons.append("missing_resource_evidence")

    update: dict[str, Any] = {
        "resource_sources": sources,
        "resource_accessibility": assessment,
    }
    if reasons:
        update["escalation_reasons"] = reasons
    return update
