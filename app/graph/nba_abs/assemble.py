"""NBA / ABS draft answer + claim collection for the shared verifier."""

from __future__ import annotations

from typing import Any

from graph.product_review.common import merge_sources
from graph.shared.verifier import dedupe_claims


def abs_assemble_node(state: dict[str, Any]) -> dict[str, Any]:
    sources = merge_sources(state.get("applicability_sources"), state.get("rate_sources"))
    lines = ["AyurDisha NBA / ABS Calculator (decision support — not legal advice)."]
    lines.append(f"Product: {state.get('product')}")

    for b in state.get("botanicals") or []:
        lines.append(
            f"Biological resource: {b.input_term} -> {b.botanical_name or 'unresolved'} "
            f"(status={b.status.value})"
        )

    applicability = state.get("applicability")
    if applicability is not None:
        lines.append(f"ABS applicability: {applicability.status.value}.")
        if applicability.summary:
            lines.append(applicability.summary)

    selection = state.get("rate_selection")
    if selection is not None and selection.rationale:
        lines.append(selection.rationale)

    calc = state.get("calculation")
    if calc is not None:
        origin = "user-supplied rate" if calc.percentage_origin == "user_override" else (
            f"rate from source {calc.source_id}"
        )
        lines.append(
            f"[CALCULATION] fee = {calc.annual_turnover_inr:,.2f} x {calc.percentage} / 100 "
            f"= INR {calc.fee_inr:,.2f} ({origin})"
        )
    elif state.get("annual_turnover_inr") is None:
        lines.append("[CALCULATION] No fee computed: annual turnover not provided.")
    else:
        lines.append("[CALCULATION] No fee computed (see escalation reasons).")

    if sources:
        lines.append("Evidence source_ids: " + ", ".join(s.id for s in sources) + ".")
    else:
        lines.append("No retrieved sources — insufficient evidence.")

    update: dict[str, Any] = {
        "retrieved_sources": sources,
        "retrieval_insufficient": not sources,
        "final_answer": "\n".join(lines),
    }
    if not sources:
        update["escalation_reasons"] = ["missing_evidence"]
    return update


def collect_abs_claims(state: dict[str, Any]) -> list[str]:
    """Structured legal claims only — the deterministic calculation line is not an LLM claim."""
    claims: list[str] = []
    applicability = state.get("applicability")
    if applicability is not None:
        claims.append(applicability.summary)
        if applicability.authority:
            claims.append(f"Competent authority: {applicability.authority}")
        claims.extend(f.summary for f in applicability.reasons)
        claims.extend(f.summary for f in applicability.exemptions_considered)

    selection = state.get("rate_selection")
    if selection is not None and state.get("percentage_override") is None:
        claims.append(selection.rationale)
        if selection.tier_description:
            claims.append(selection.tier_description)
    return dedupe_claims([c for c in claims if c])
