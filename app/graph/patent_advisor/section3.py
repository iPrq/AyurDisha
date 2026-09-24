"""Section 3 scorer — NVIDIA NIM structured analysis + Python risk weights."""

from __future__ import annotations

from typing import Any

from config import Settings, get_settings
from graph.models import LegalScope, RetrievedSource, Section3Results
from graph.patent_advisor.risk import calculate_patentability_risk
from graph.prompts import SECTION3_SYSTEM, legal_scope_instruction
from graph.state import PatentAdvisorState
from llm.provider import get_chat_model
from llm.structured import format_sources_for_prompt, structured_invoke


def _coerce_scope(value: Any) -> LegalScope:
    if isinstance(value, LegalScope):
        return value
    return LegalScope(str(value or "domestic").lower())


def score_section3(
    sources: list[RetrievedSource],
    *,
    jurisdiction: str = "india",
    legal_scope: LegalScope | str = LegalScope.DOMESTIC,
    botanical_name: str | None = None,
    product: str | None = None,
    llm: Any | None = None,
    settings: Settings | None = None,
) -> Section3Results:
    """LLM-based Section 3 analysis grounded only in retrieved sources."""
    cfg = settings or get_settings()
    model = llm if llm is not None else get_chat_model(settings=cfg)
    scope = _coerce_scope(legal_scope)

    if not sources:
        return Section3Results(
            provisions=[],
            summary=(
                "Insufficient evidence: no retrieved sources. "
                "Human review required — do not invent statute text."
            ),
            jurisdiction=jurisdiction,
            legal_scope=scope,
            insufficient_evidence=True,
        )

    if scope == LegalScope.INTERNATIONAL and not any(
        s.legal_scope == LegalScope.INTERNATIONAL for s in sources
    ):
        return Section3Results(
            provisions=[],
            summary=(
                "Insufficient international/comparative evidence. "
                "Human review required — foreign law not invented."
            ),
            jurisdiction=jurisdiction,
            legal_scope=scope,
            insufficient_evidence=True,
        )

    user = "\n".join(
        [
            legal_scope_instruction(scope, jurisdiction),
            f"product={product or ''}",
            f"botanical_name={botanical_name or ''}",
            f"jurisdiction={jurisdiction}",
            "Analyze 3(d), 3(e), 3(p) only where retrieved evidence supports it.",
            "Cite evidence_source_ids from the sources below only.",
            "Do not invent statutes or foreign law.",
            "Retrieved sources:",
            format_sources_for_prompt(sources),
        ]
    )

    result = structured_invoke(
        model, Section3Results, system=SECTION3_SYSTEM, user=user
    )
    result.jurisdiction = jurisdiction
    result.legal_scope = scope
    # Sanitize: only allow evidence ids that exist
    valid_ids = {s.id for s in sources}
    for provision in result.provisions:
        provision.evidence_source_ids = [
            i for i in provision.evidence_source_ids if i in valid_ids
        ]
        if provision.triggered and not provision.evidence_source_ids:
            provision.triggered = False
            provision.reason = (
                provision.reason
                + " [trigger cleared: no valid retrieved source_id]"
            ).strip()
    return result


def section3_scorer_node(
    state: PatentAdvisorState,
    *,
    settings: Settings | None = None,
    llm: Any | None = None,
) -> dict[str, Any]:
    sources = list(state.get("retrieved_sources") or [])
    section3 = score_section3(
        sources,
        jurisdiction=state.get("jurisdiction") or "india",
        legal_scope=state.get("legal_scope") or LegalScope.DOMESTIC,
        botanical_name=state.get("botanical_name"),
        product=state.get("product"),
        llm=llm,
        settings=settings,
    )
    risk = calculate_patentability_risk(section3, settings=settings or get_settings())
    update: dict[str, Any] = {
        "section3": section3,
        "patentability_risk": risk,
        "patentability_risk_score": risk.score,
    }
    if section3.insufficient_evidence:
        reasons = list(state.get("escalation_reasons") or [])
        if "missing_evidence" not in reasons:
            reasons.append("missing_evidence")
        update["escalation_reasons"] = reasons
    return update
