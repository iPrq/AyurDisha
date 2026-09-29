"""Prior-art advisor — NVIDIA NIM, retrieved-evidence only."""

from __future__ import annotations

from typing import Any

from graph.models import LegalScope, PriorArtResult, RetrievedSource
from graph.prompts import PRIOR_ART_SYSTEM, document_context_block, legal_scope_instruction
from graph.state import PatentAdvisorState
from llm.provider import get_chat_model
from llm.structured import format_sources_for_prompt, structured_invoke


def _coerce_scope(value: Any) -> LegalScope:
    if isinstance(value, LegalScope):
        return value
    return LegalScope(str(value or "domestic").lower())


def analyze_prior_art(
    sources: list[RetrievedSource],
    *,
    legal_scope: LegalScope | str = LegalScope.DOMESTIC,
    botanical_name: str | None = None,
    product: str | None = None,
    llm: Any | None = None,
    document_text: str | None = None,
) -> PriorArtResult:
    scope = _coerce_scope(legal_scope)
    model = llm if llm is not None else get_chat_model()

    if not sources:
        return PriorArtResult(
            findings=[],
            summary=(
                "Insufficient prior-art evidence in retrieved sources. "
                "No patents or disclosures invented."
            ),
            insufficient_evidence=True,
            legal_scope=scope,
        )

    user = "\n".join(
        [
            legal_scope_instruction(scope),
            f"product={product or ''}",
            f"botanical_name={botanical_name or ''}",
            "Summarize prior-art / patent-information findings ONLY from sources below.",
            "Never invent patent numbers, titles, or URLs.",
            *document_context_block(document_text),
            "Retrieved sources:",
            format_sources_for_prompt(sources),
        ]
    )
    result = structured_invoke(
        model, PriorArtResult, system=PRIOR_ART_SYSTEM, user=user
    )
    result.legal_scope = scope
    valid_ids = {s.id for s in sources}
    for finding in result.findings:
        finding.evidence_source_ids = [
            i for i in finding.evidence_source_ids if i in valid_ids
        ]
    if not result.findings:
        result.insufficient_evidence = True
    return result


def prior_art_node(
    state: PatentAdvisorState,
    *,
    llm: Any | None = None,
) -> dict[str, Any]:
    sources = list(state.get("retrieved_sources") or [])
    result = analyze_prior_art(
        sources,
        legal_scope=state.get("legal_scope") or LegalScope.DOMESTIC,
        botanical_name=state.get("botanical_name"),
        product=state.get("product"),
        llm=llm,
        document_text=state.get("document_text"),
    )
    update: dict[str, Any] = {"prior_art": result}
    if result.insufficient_evidence:
        reasons = list(state.get("escalation_reasons") or [])
        if "missing_prior_art_evidence" not in reasons:
            reasons.append("missing_prior_art_evidence")
        update["escalation_reasons"] = reasons
    return update
