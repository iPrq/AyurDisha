"""Product Review aggregator — keeps the three dimensions separate; no combined score."""

from __future__ import annotations

from typing import Any

from graph.product_review.common import merge_sources, target_market
from graph.shared.verifier import dedupe_claims, draft_sentences


def _dimension_line(label: str, assessment: Any) -> str:
    if assessment is None:
        return f"{label}: not assessed."
    return f"{label}: {assessment.rating.value}. {assessment.summary}".strip()


def product_review_aggregator_node(state: dict[str, Any]) -> dict[str, Any]:
    sources = merge_sources(
        state.get("legal_sources"),
        state.get("market_sources"),
        state.get("resource_sources"),
    )

    dimension_lines = [
        _dimension_line("Market Feasibility", state.get("market_feasibility")),
        _dimension_line("Legal Compliance", state.get("legal_compliance")),
        _dimension_line("Resource Accessibility", state.get("resource_accessibility")),
    ]
    combined = (
        "Each dimension is assessed independently (no combined score). "
        + " ".join(dimension_lines)
    )

    lines = [
        "AyurDisha Product Review (decision support — not legal or investment advice).",
        f"Product: {state.get('product')}",
        f"Target market: {target_market(state)} | legal_scope: {state.get('legal_scope')}",
    ]
    for b in state.get("botanicals") or []:
        lines.append(
            f"Botanical: {b.input_term} -> {b.botanical_name or 'unresolved'} "
            f"(status={b.status.value})"
        )
    lines.extend(dimension_lines)
    if sources:
        lines.append("Evidence source_ids: " + ", ".join(s.id for s in sources) + ".")
    else:
        lines.append("No retrieved sources — insufficient evidence.")

    update: dict[str, Any] = {
        "retrieved_sources": sources,
        "retrieval_insufficient": not sources,
        "combined_summary": combined,
        "final_answer": "\n".join(lines),
    }
    if not sources:
        update["escalation_reasons"] = ["missing_evidence"]
    return update


def collect_product_review_claims(state: dict[str, Any]) -> list[str]:
    claims: list[str] = []

    market = state.get("market_feasibility")
    if market is not None:
        claims.append(market.summary)
        claims.extend(f.summary for f in market.findings)
        claims.extend(f.summary for f in market.demand_indicators)
        claims.extend(
            f"Competitor: {c.name}" + (f" ({c.company})" if c.company else "")
            for c in market.competitors
        )

    legal = state.get("legal_compliance")
    if legal is not None:
        claims.append(legal.summary)
        if legal.regulatory_category:
            claims.append(f"Regulatory category: {legal.regulatory_category}")
        claims.extend(f.summary for f in legal.requirements)
        claims.extend(f.summary for f in legal.restrictions)

    resource = state.get("resource_accessibility")
    if resource is not None:
        claims.append(resource.summary)
        claims.extend(f.summary for f in resource.findings)
        for r in resource.resources:
            for text in (r.availability, r.cultivation, r.sustainability_concerns):
                if text:
                    claims.append(f"{r.botanical_name or r.ingredient}: {text}")

    claims.extend(draft_sentences(state.get("final_answer")))
    return dedupe_claims([c for c in claims if c])
