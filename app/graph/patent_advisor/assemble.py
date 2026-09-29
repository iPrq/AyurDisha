"""Draft final answer assembler (pre-verifier)."""

from __future__ import annotations

from typing import Any

from graph.state import PatentAdvisorState


def assemble_draft_answer(state: PatentAdvisorState) -> dict[str, Any]:
    """Compose a draft final_answer from structured fields for the verifier."""
    lines: list[str] = [
        "AyurDisha Patent Advisor (decision support — not legal advice).",
        f"Product: {state.get('product')}",
        f"Jurisdiction: {state.get('jurisdiction')} | legal_scope: {state.get('legal_scope')}",
    ]

    botanical = state.get("botanical")
    if botanical is not None:
        lines.append(
            f"Botanical: {botanical.botanical_name or 'unresolved'} "
            f"(status={botanical.status.value}, confidence={botanical.confidence:.2f})"
        )

    section3 = state.get("section3")
    if section3 is not None and section3.summary:
        lines.append(section3.summary)

    risk = state.get("patentability_risk")
    if risk is not None:
        lines.append(
            f"Patentability risk indicator (rule-based): {risk.score:.2f}. {risk.disclaimer}"
        )

    grant = state.get("grant_likelihood")
    if grant is not None and grant.probability is not None:
        lines.append(
            f"Estimated grant probability (AI, uncalibrated): {grant.probability:.0%} "
            f"(confidence: {grant.confidence}). {grant.disclaimer}"
        )

    prior_art = state.get("prior_art")
    if prior_art is not None and prior_art.summary:
        lines.append(prior_art.summary)

    ip_routes = state.get("ip_routes")
    if ip_routes is not None and ip_routes.summary:
        lines.append(ip_routes.summary)

    sources = state.get("retrieved_sources") or []
    if sources:
        lines.append(
            "Evidence source_ids: " + ", ".join(s.id for s in sources) + "."
        )
    else:
        lines.append("No retrieved sources — insufficient evidence.")

    return {"final_answer": "\n".join(lines)}
