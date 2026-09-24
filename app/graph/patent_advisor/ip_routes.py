"""IP route analysis — NVIDIA NIM structured pathway suggestions."""

from __future__ import annotations

from typing import Any

from graph.models import (
    IPRouteAnalysis,
    LegalScope,
    RetrievedSource,
    Section3Results,
)
from graph.prompts import IP_ROUTES_SYSTEM, legal_scope_instruction
from graph.state import PatentAdvisorState
from llm.provider import get_chat_model
from llm.structured import format_sources_for_prompt, structured_invoke


def _coerce_scope(value: Any) -> LegalScope:
    if isinstance(value, LegalScope):
        return value
    return LegalScope(str(value or "domestic").lower())


def analyze_ip_routes(
    sources: list[RetrievedSource],
    *,
    section3: Section3Results | None = None,
    legal_scope: LegalScope | str = LegalScope.DOMESTIC,
    patentability_risk_score: float | None = None,
    botanical_name: str | None = None,
    product: str | None = None,
    llm: Any | None = None,
) -> IPRouteAnalysis:
    scope = _coerce_scope(legal_scope)
    model = llm if llm is not None else get_chat_model()

    if not sources:
        return IPRouteAnalysis(
            suggestions=[],
            summary="Insufficient evidence for IP pathway suggestions.",
            insufficient_evidence=True,
            legal_scope=scope,
        )

    if scope == LegalScope.INTERNATIONAL and not any(
        s.legal_scope == LegalScope.INTERNATIONAL for s in sources
    ):
        return IPRouteAnalysis(
            suggestions=[],
            summary=(
                "International legal_scope requested but no comparative sources "
                "retrieved — pathways not suggested; human review required."
            ),
            insufficient_evidence=True,
            legal_scope=scope,
        )

    section3_json = section3.model_dump_json() if section3 is not None else "{}"
    user = "\n".join(
        [
            legal_scope_instruction(scope),
            f"product={product or ''}",
            f"botanical_name={botanical_name or ''}",
            f"patentability_risk_score={patentability_risk_score}",
            "section3_json:",
            section3_json,
            "Suggest Patent, Trademark, Design, Trade Secret appropriateness.",
            "Ground only in retrieved evidence + section3 findings. Not legal advice.",
            "Retrieved sources:",
            format_sources_for_prompt(sources),
        ]
    )
    result = structured_invoke(
        model, IPRouteAnalysis, system=IP_ROUTES_SYSTEM, user=user
    )
    result.legal_scope = scope
    valid_ids = {s.id for s in sources}
    for suggestion in result.suggestions:
        suggestion.evidence_source_ids = [
            i for i in suggestion.evidence_source_ids if i in valid_ids
        ]
    return result


def ip_routes_node(
    state: PatentAdvisorState,
    *,
    llm: Any | None = None,
) -> dict[str, Any]:
    sources = list(state.get("retrieved_sources") or [])
    result = analyze_ip_routes(
        sources,
        section3=state.get("section3"),
        legal_scope=state.get("legal_scope") or LegalScope.DOMESTIC,
        patentability_risk_score=state.get("patentability_risk_score"),
        botanical_name=state.get("botanical_name"),
        product=state.get("product"),
        llm=llm,
    )
    update: dict[str, Any] = {"ip_routes": result}
    if result.insufficient_evidence:
        reasons = list(state.get("escalation_reasons") or [])
        if "missing_evidence" not in reasons:
            reasons.append("missing_evidence")
        update["escalation_reasons"] = reasons
    return update
