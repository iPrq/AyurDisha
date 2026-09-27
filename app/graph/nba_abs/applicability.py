"""NBA / ABS applicability — retrieved Biological Diversity Act sources + NIM reasoning."""

from __future__ import annotations

from typing import Any

from config import Settings, get_settings
from graph.models import (
    AbsApplicability,
    AbsApplicabilityStatus,
    LegalScope,
    RetrievedSource,
)
from graph.product_review.common import botanical_context, sanitize_findings
from graph.prompts import ABS_APPLICABILITY_SYSTEM
from llm.provider import get_chat_model
from llm.structured import format_sources_for_prompt, structured_invoke
from retrieval.base import LegalRetriever
from retrieval.mock import get_mock_retriever

ABS_SOURCE_TYPES = ["regulation", "statute", "guideline"]


def _value(v: Any) -> str:
    return v.value if hasattr(v, "value") else str(v or "")


def request_facts(state: dict[str, Any]) -> list[str]:
    return [
        f"product={state.get('product') or ''}",
        f"purpose={_value(state.get('purpose'))}",
        f"entity_type={_value(state.get('entity_type'))}",
        f"resource_source={_value(state.get('resource_source'))}",
        f"jurisdiction={state.get('jurisdiction') or 'india'}",
    ]


def build_applicability_query(state: dict[str, Any]) -> str:
    return " ".join(
        [
            "Biological Diversity Act access biological resources approval",
            "National Biodiversity Authority State Biodiversity Board exemption",
            _value(state.get("purpose")).replace("_", " "),
            *(b.botanical_name or b.input_term for b in state.get("botanicals") or []),
        ]
    )


def analyze_applicability(
    state: dict[str, Any],
    sources: list[RetrievedSource],
    *,
    llm: Any,
) -> AbsApplicability:
    if not sources:
        return AbsApplicability(
            status=AbsApplicabilityStatus.UNCERTAIN,
            summary="Insufficient ABS evidence: no Biological Diversity sources retrieved.",
            insufficient_evidence=True,
        )

    user = "\n".join(
        [
            *request_facts(state),
            "Biological resources (botanical normalization):",
            botanical_context(state),
            "Decide ABS applicability from the sources below only; cite evidence_source_ids.",
            "Retrieved sources:",
            format_sources_for_prompt(sources),
        ]
    )
    result = structured_invoke(
        llm, AbsApplicability, system=ABS_APPLICABILITY_SYSTEM, user=user
    )
    valid = {s.id for s in sources}
    sanitize_findings(result.reasons, valid)
    sanitize_findings(result.exemptions_considered, valid)
    if not any(f.evidence_source_ids for f in result.reasons + result.exemptions_considered):
        result.status = AbsApplicabilityStatus.UNCERTAIN
        result.insufficient_evidence = True
    return result


def abs_applicability_node(
    state: dict[str, Any],
    *,
    retriever: LegalRetriever | None = None,
    settings: Settings | None = None,
    llm: Any | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    model = llm if llm is not None else get_chat_model(settings=cfg)
    client = retriever or get_mock_retriever()

    sources = client.retrieve(
        build_applicability_query(state),
        jurisdiction=state.get("jurisdiction") or "india",
        legal_scope=LegalScope.DOMESTIC,
        top_k=6,
        source_types=ABS_SOURCE_TYPES,
    )
    result = analyze_applicability(state, sources, llm=model)

    reasons: list[str] = []
    if result.insufficient_evidence:
        reasons.append("missing_abs_evidence")
    if result.status == AbsApplicabilityStatus.UNCERTAIN:
        reasons.append("abs_applicability_uncertain")

    update: dict[str, Any] = {
        "applicability_sources": sources,
        "applicability": result,
    }
    if reasons:
        update["escalation_reasons"] = reasons
    return update
