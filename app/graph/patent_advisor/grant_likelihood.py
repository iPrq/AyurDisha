"""Grant likelihood — NVIDIA NIM estimate of patent grant probability (uncalibrated)."""

from __future__ import annotations

from typing import Any

from graph.models import (
    GrantLikelihoodEstimate,
    IPRouteAnalysis,
    PriorArtResult,
    RetrievedSource,
    Section3Results,
)
from graph.prompts import GRANT_LIKELIHOOD_SYSTEM, document_context_block
from graph.state import PatentAdvisorState
from llm.provider import get_chat_model
from llm.structured import format_sources_for_prompt, structured_invoke


def estimate_grant_likelihood(
    sources: list[RetrievedSource],
    *,
    section3: Section3Results | None = None,
    patentability_risk_score: float | None = None,
    prior_art: PriorArtResult | None = None,
    ip_routes: IPRouteAnalysis | None = None,
    botanical_name: str | None = None,
    product: str | None = None,
    llm: Any | None = None,
    document_text: str | None = None,
) -> GrantLikelihoodEstimate:
    if not sources:
        return GrantLikelihoodEstimate(
            probability=None,
            confidence="low",
            rationale="No retrieved sources — grant probability not estimated.",
            insufficient_evidence=True,
        )

    model = llm if llm is not None else get_chat_model()
    section3_json = section3.model_dump_json() if section3 is not None else "{}"
    user = "\n".join(
        [
            f"product={product or ''}",
            f"botanical_name={botanical_name or ''}",
            f"section3_rule_based_risk_score={patentability_risk_score}",
            "section3_json:",
            section3_json,
            f"prior_art_summary={prior_art.summary if prior_art else ''}",
            f"ip_routes_summary={ip_routes.summary if ip_routes else ''}",
            "Estimate the probability of patent grant in India. Not legal advice.",
            *document_context_block(document_text),
            "Retrieved sources:",
            format_sources_for_prompt(sources),
        ]
    )
    result = structured_invoke(
        model, GrantLikelihoodEstimate, system=GRANT_LIKELIHOOD_SYSTEM, user=user
    )
    valid_ids = {s.id for s in sources}
    result.evidence_source_ids = [i for i in result.evidence_source_ids if i in valid_ids]
    if result.probability is not None:
        result.probability = min(1.0, max(0.0, result.probability))
    return result


def grant_likelihood_node(
    state: PatentAdvisorState,
    *,
    llm: Any | None = None,
) -> dict[str, Any]:
    result = estimate_grant_likelihood(
        list(state.get("retrieved_sources") or []),
        section3=state.get("section3"),
        patentability_risk_score=state.get("patentability_risk_score"),
        prior_art=state.get("prior_art"),
        ip_routes=state.get("ip_routes"),
        botanical_name=state.get("botanical_name"),
        product=state.get("product"),
        llm=llm,
        document_text=state.get("document_text"),
    )
    return {"grant_likelihood": result}
