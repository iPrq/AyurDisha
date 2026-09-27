"""Section 3 scorer — NVIDIA NIM structured analysis + Python risk weights."""

from __future__ import annotations

import re
from typing import Any

from config import Settings, get_settings
from graph.models import (
    SUPPORTED_SECTION3_CLAUSES,
    LegalScope,
    RetrievedSource,
    Section3Clause,
    Section3Results,
    normalize_section3_clause_ref,
)
from graph.patent_advisor.risk import calculate_patentability_risk
from graph.prompts import SECTION3_SYSTEM, legal_scope_instruction
from graph.state import PatentAdvisorState
from llm.provider import get_chat_model
from llm.structured import format_sources_for_prompt, structured_invoke


def _coerce_scope(value: Any) -> LegalScope:
    if isinstance(value, LegalScope):
        return value
    return LegalScope(str(value or "domestic").lower())


_CLAUSE_LABEL_RE = re.compile(r"^3\([a-z]\)$")

TRIGGER_CLEARED_NOTE = (
    "[trigger cleared: no valid retrieved source_id for this clause — "
    "evidence gap, human review required]"
)


def _clause_label(source: RetrievedSource) -> str | None:
    """Explicit Section 3 clause label of a source (e.g. "3(d)"); None if unlabeled."""
    ref = normalize_section3_clause_ref(source.section or "")
    if isinstance(ref, str) and _CLAUSE_LABEL_RE.match(ref):
        return ref
    return None


def _clause_value(clause: Section3Clause | str) -> str:
    return clause.value if isinstance(clause, Section3Clause) else str(clause)


def sanitize_section3_evidence(
    result: Section3Results, sources: list[RetrievedSource]
) -> Section3Results:
    """Validate evidence_source_ids in Python; clear unsupported triggers as evidence gaps.

    An id is valid for a provision only if it belongs to a retrieved source AND that
    source is either unlabeled (guideline, preamble, patent, ...) or labeled with the
    same Section 3 clause. Evidence-gap fields are owned by Python, not the LLM.
    """
    by_id = {s.id: s for s in sources}
    result.evidence_gap_clauses = []
    for provision in result.provisions:
        clause_ref = _clause_value(provision.clause)
        provision.evidence_gap = False
        provision.evidence_source_ids = [
            i
            for i in provision.evidence_source_ids
            if i in by_id and _clause_label(by_id[i]) in (None, clause_ref)
        ]
        if provision.triggered and not provision.evidence_source_ids:
            provision.triggered = False
            provision.evidence_gap = True
            provision.reason = (provision.reason + " " + TRIGGER_CLEARED_NOTE).strip()
            if provision.clause not in result.evidence_gap_clauses:
                result.evidence_gap_clauses.append(provision.clause)
    return result


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
            "Analyze only these Section 3 clauses, and only where retrieved evidence "
            f"supports it: {', '.join(SUPPORTED_SECTION3_CLAUSES)}. Never return 3(g).",
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
    # Sanitize: only allow evidence ids that exist and belong to the clause
    return sanitize_section3_evidence(result, sources)


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
    new_reasons: list[str] = []
    if section3.insufficient_evidence:
        new_reasons.append("missing_evidence")
    if section3.evidence_gap_clauses:
        new_reasons.append("section3_evidence_gap")
    if section3.rejected_clauses:
        new_reasons.append("unsupported_section3_clause")
    if new_reasons:
        reasons = list(state.get("escalation_reasons") or [])
        for reason in new_reasons:
            if reason not in reasons:
                reasons.append(reason)
        update["escalation_reasons"] = reasons
    return update
