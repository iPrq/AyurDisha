"""Shared Critic Verifier — NVIDIA NIM source-grounded claim checking."""

from __future__ import annotations

import re
from typing import Any

from config import Settings, get_settings
from graph.models import (
    BotanicalStatus,
    ClaimSupportStatus,
    ClaimVerification,
    RetrievedSource,
    VerificationOutcome,
    VerificationResult,
)
from graph.prompts import VERIFIER_SYSTEM
from graph.state import PatentAdvisorState
from llm.provider import get_chat_model
from llm.structured import format_sources_for_prompt, structured_invoke


# Escalation reasons that always force HUMAN_REVIEW_REQUIRED.
HUMAN_REVIEW_REASONS = (
    "ambiguous_botanical",
    "insufficient_international_evidence",
    "section3_evidence_gap",
)


def collect_claims_from_state(state: PatentAdvisorState) -> list[str]:
    claims: list[str] = []

    section3 = state.get("section3")
    if section3 is not None:
        if section3.summary:
            claims.append(section3.summary)
        for provision in section3.provisions:
            if provision.reason:
                clause = (
                    provision.clause.value
                    if hasattr(provision.clause, "value")
                    else provision.clause
                )
                claims.append(f"{clause}: {provision.reason}")

    prior_art = state.get("prior_art")
    if prior_art is not None:
        if prior_art.summary:
            claims.append(prior_art.summary)
        for finding in prior_art.findings:
            claims.append(finding.summary)

    ip_routes = state.get("ip_routes")
    if ip_routes is not None:
        if ip_routes.summary:
            claims.append(ip_routes.summary)
        for suggestion in ip_routes.suggestions:
            if suggestion.rationale:
                route = (
                    suggestion.route.value
                    if hasattr(suggestion.route, "value")
                    else suggestion.route
                )
                claims.append(f"{route}: {suggestion.rationale}")

    draft = state.get("final_answer")
    if isinstance(draft, str) and draft.strip():
        for part in re.split(r"(?<=[.!?])\s+", draft.strip()):
            if part.strip():
                claims.append(part.strip())

    seen: set[str] = set()
    unique: list[str] = []
    for c in claims:
        key = c.strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(key)
    return unique


def verify_claims(
    claims: list[str],
    sources: list[RetrievedSource],
    *,
    escalation_reasons: list[str] | None = None,
    settings: Settings | None = None,
    llm: Any | None = None,
) -> VerificationResult:
    """Verify claims via NIM; apply escalation rules in Python."""
    cfg = settings or get_settings()
    model = llm if llm is not None else get_chat_model(settings=cfg)
    reasons = list(escalation_reasons or [])

    if not sources:
        reasons.append("missing_evidence")
        return VerificationResult(
            outcome=VerificationOutcome.HUMAN_REVIEW_REQUIRED,
            claims=[
                ClaimVerification(
                    claim=c,
                    status=ClaimSupportStatus.UNSUPPORTED,
                    evidence_source_ids=[],
                    notes="No retrieved sources.",
                )
                for c in claims
            ],
            stripped_unsupported_claims=list(claims),
            escalation_reasons=_dedupe(reasons),
            notes="Missing evidence — escalated.",
        )

    if not claims:
        return VerificationResult(
            outcome=VerificationOutcome.PASS,
            claims=[],
            stripped_unsupported_claims=[],
            escalation_reasons=_dedupe(reasons),
            notes="No claims to verify.",
        )

    user = "\n".join(
        [
            "Verify each claim against retrieved sources only.",
            "Mark SUPPORTED / PARTIALLY_SUPPORTED / UNSUPPORTED.",
            "List unsupported claims in stripped_unsupported_claims.",
            "Claims:",
            *[f"- {c}" for c in claims],
            "Retrieved sources:",
            format_sources_for_prompt(sources),
        ]
    )
    result = structured_invoke(
        model, VerificationResult, system=VERIFIER_SYSTEM, user=user
    )

    valid_ids = {s.id for s in sources}
    for claim in result.claims:
        claim.evidence_source_ids = [
            i for i in claim.evidence_source_ids if i in valid_ids
        ]

    stripped = list(result.stripped_unsupported_claims) or [
        v.claim
        for v in result.claims
        if v.status == ClaimSupportStatus.UNSUPPORTED
    ]
    result.stripped_unsupported_claims = stripped

    supported = sum(
        1
        for v in result.claims
        if v.status
        in {ClaimSupportStatus.SUPPORTED, ClaimSupportStatus.PARTIALLY_SUPPORTED}
    )
    total = len(result.claims) or 1
    support_ratio = supported / total

    reasons.extend(result.escalation_reasons)
    if any(r in reasons for r in HUMAN_REVIEW_REASONS):
        outcome = VerificationOutcome.HUMAN_REVIEW_REQUIRED
    elif stripped and support_ratio < cfg.verification_min_support_ratio:
        outcome = VerificationOutcome.FAIL
        reasons.append("unsupported_claims")
    elif stripped:
        outcome = VerificationOutcome.HUMAN_REVIEW_REQUIRED
        reasons.append("partial_unsupported_claims")
    else:
        outcome = VerificationOutcome.PASS

    result.outcome = outcome
    result.escalation_reasons = _dedupe(reasons)
    result.notes = (
        "Source-grounded verification; unsupported claims are rejected or escalated."
    )
    return result


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out


def strip_unsupported_from_text(text: str, stripped: list[str]) -> str:
    if not text:
        return text
    result = text
    for claim in stripped:
        result = result.replace(claim, "")
    result = re.sub(r"\n{3,}", "\n\n", result).strip()
    if stripped:
        result = (
            (result + "\n\n" if result else "")
            + "[Unsupported claims were removed pending human review.]"
        )
    return result


def critic_verifier_node(
    state: PatentAdvisorState,
    *,
    settings: Settings | None = None,
    llm: Any | None = None,
) -> dict[str, Any]:
    sources = list(state.get("retrieved_sources") or [])
    claims = collect_claims_from_state(state)
    prior_reasons = list(state.get("escalation_reasons") or [])

    botanical = state.get("botanical")
    if botanical is not None and botanical.status == BotanicalStatus.AMBIGUOUS:
        if "ambiguous_botanical" not in prior_reasons:
            prior_reasons.append("ambiguous_botanical")

    if state.get("retrieval_insufficient"):
        if "missing_evidence" not in prior_reasons:
            prior_reasons.append("missing_evidence")

    legal_scope = state.get("legal_scope")
    scope_val = (
        legal_scope.value if hasattr(legal_scope, "value") else str(legal_scope or "")
    )
    if scope_val == "international" and not sources:
        if "insufficient_international_evidence" not in prior_reasons:
            prior_reasons.append("insufficient_international_evidence")

    result = verify_claims(
        claims,
        sources,
        escalation_reasons=prior_reasons,
        settings=settings,
        llm=llm,
    )

    draft = state.get("final_answer") or ""
    cleaned = strip_unsupported_from_text(draft, result.stripped_unsupported_claims)

    return {
        "verification": result,
        "verification_status": result.outcome.value,
        "escalation_reasons": result.escalation_reasons,
        "final_answer": cleaned or draft,
    }


def make_critic_verifier_node(*, settings: Settings | None = None, llm: Any | None = None):
    def _node(state: PatentAdvisorState) -> dict[str, Any]:
        return critic_verifier_node(state, settings=settings, llm=llm)

    return _node
