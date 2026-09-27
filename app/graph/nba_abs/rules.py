"""ABS rule retrieval + rate selection. The LLM picks the rate; Python checks grounding."""

from __future__ import annotations

from typing import Any

from config import Settings, get_settings
from graph.models import AbsRateSelection, LegalScope, RetrievedSource
from graph.nba_abs.applicability import ABS_SOURCE_TYPES, request_facts
from graph.nba_abs.calculator import percentage_is_grounded
from graph.prompts import ABS_RATE_SYSTEM
from llm.provider import get_chat_model
from llm.structured import format_sources_for_prompt, structured_invoke
from retrieval.base import LegalRetriever
from retrieval.mock import get_mock_retriever


def build_rate_query(state: dict[str, Any]) -> str:
    purpose = str(getattr(state.get("purpose"), "value", state.get("purpose")) or "")
    return (
        "benefit sharing percentage annual gross ex-factory sale turnover "
        f"{purpose.replace('_', ' ')} biological resources"
    )


def _turnover_line(turnover: float | None) -> str:
    if turnover is None:
        return "annual_turnover_inr=not provided"
    # Crore conversion is a reading aid for slab matching, not the fee calculation.
    return f"annual_turnover_inr={turnover:,.2f} (= {turnover / 1e7:,.4f} crore)"


def select_rate(
    state: dict[str, Any],
    sources: list[RetrievedSource],
    *,
    llm: Any,
) -> AbsRateSelection:
    if not sources:
        return AbsRateSelection(
            rationale="No benefit-sharing rule sources retrieved.",
            insufficient_evidence=True,
        )

    user = "\n".join(
        [
            *request_facts(state),
            _turnover_line(state.get("annual_turnover_inr")),
            "Select the applicable benefit-sharing percentage from the sources below only. "
            "Quote the exact rule text in quoted_text and give its source_id.",
            "Retrieved sources:",
            format_sources_for_prompt(sources),
        ]
    )
    result = structured_invoke(llm, AbsRateSelection, system=ABS_RATE_SYSTEM, user=user)
    if result.source_id not in {s.id for s in sources}:
        result.source_id = None
    result.grounded = result.percentage is not None and percentage_is_grounded(
        result.percentage, result.source_id, sources
    )
    if result.percentage is None:
        result.insufficient_evidence = True
    return result


def abs_rule_retrieval_node(
    state: dict[str, Any],
    *,
    retriever: LegalRetriever | None = None,
    settings: Settings | None = None,
    llm: Any | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    client = retriever or get_mock_retriever()

    sources = client.retrieve(
        build_rate_query(state),
        jurisdiction=state.get("jurisdiction") or "india",
        legal_scope=LegalScope.DOMESTIC,
        top_k=5,
        source_types=ABS_SOURCE_TYPES,
    )

    override = state.get("percentage_override")
    if override is not None:
        selection = AbsRateSelection(
            percentage=float(override),
            rationale="User-supplied percentage override; not selected from retrieved sources.",
        )
    else:
        model = llm if llm is not None else get_chat_model(settings=cfg)
        selection = select_rate(state, sources, llm=model)

    return {"rate_sources": sources, "rate_selection": selection}
