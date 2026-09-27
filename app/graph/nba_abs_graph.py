"""LangGraph workflow: NBA / ABS Calculator (deterministic Python fee arithmetic)."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from config import Settings, get_settings
from graph.models import AbsApplicabilityStatus
from graph.nba_abs.applicability import abs_applicability_node
from graph.nba_abs.assemble import abs_assemble_node, collect_abs_claims
from graph.nba_abs.calculator import abs_calculation_node
from graph.nba_abs.rules import abs_rule_retrieval_node
from graph.shared.botanical import multi_botanical_normalizer_node
from graph.shared.input_parser import input_parser_node
from graph.shared.verifier import critic_verifier_node
from graph.state import NbaAbsState
from knowledge_graph.base import BotanicalKnowledgeGraph
from llm.provider import get_chat_model
from retrieval.base import LegalRetriever

ABS_HUMAN_REVIEW_REASONS = frozenset(
    {
        "missing_abs_evidence",
        "abs_applicability_uncertain",
        "missing_abs_rate_evidence",
        "rate_not_grounded_in_source",
    }
)


def route_after_applicability(state: NbaAbsState) -> str:
    applicability = state.get("applicability")
    not_applicable = (
        applicability is not None
        and applicability.status == AbsApplicabilityStatus.NOT_APPLICABLE
    )
    if not_applicable and state.get("percentage_override") is None:
        return "assemble"
    return "rule_retrieval"


def build_nba_abs_graph(
    *,
    kg: BotanicalKnowledgeGraph | None = None,
    retriever: LegalRetriever | None = None,
    settings: Settings | None = None,
    llm: Any | None = None,
):
    cfg = settings or get_settings()
    model = llm if llm is not None else get_chat_model(settings=cfg)

    def _botanical(state: NbaAbsState) -> dict[str, Any]:
        return multi_botanical_normalizer_node(state, kg=kg, settings=cfg, llm=model)

    def _applicability(state: NbaAbsState) -> dict[str, Any]:
        return abs_applicability_node(state, retriever=retriever, settings=cfg, llm=model)

    def _rules(state: NbaAbsState) -> dict[str, Any]:
        return abs_rule_retrieval_node(state, retriever=retriever, settings=cfg, llm=model)

    def _verifier(state: NbaAbsState) -> dict[str, Any]:
        return critic_verifier_node(
            state,
            settings=cfg,
            llm=model,
            claims_collector=collect_abs_claims,
            human_review_reasons=ABS_HUMAN_REVIEW_REASONS,
        )

    graph = StateGraph(NbaAbsState)
    graph.add_node("input_parser", input_parser_node)
    graph.add_node("botanical", _botanical)
    graph.add_node("applicability", _applicability)
    graph.add_node("rule_retrieval", _rules)
    graph.add_node("calculation", abs_calculation_node)
    graph.add_node("assemble", abs_assemble_node)
    graph.add_node("verifier", _verifier)

    graph.add_edge(START, "input_parser")
    graph.add_edge("input_parser", "botanical")
    graph.add_edge("botanical", "applicability")
    graph.add_conditional_edges(
        "applicability",
        route_after_applicability,
        {"rule_retrieval": "rule_retrieval", "assemble": "assemble"},
    )
    graph.add_edge("rule_retrieval", "calculation")
    graph.add_edge("calculation", "assemble")
    graph.add_edge("assemble", "verifier")
    graph.add_edge("verifier", END)

    return graph.compile()


def run_nba_abs(
    *,
    product: str,
    ingredients: list[str] | None = None,
    annual_turnover_inr: float | None = None,
    purpose: str = "commercial_utilization",
    entity_type: str = "indian",
    resource_source: str = "unknown",
    percentage_override: float | None = None,
    language: str = "en",
    jurisdiction: str = "india",
    user_query: str | None = None,
    kg: BotanicalKnowledgeGraph | None = None,
    retriever: LegalRetriever | None = None,
    settings: Settings | None = None,
    llm: Any | None = None,
) -> dict[str, Any]:
    app = build_nba_abs_graph(kg=kg, retriever=retriever, settings=settings, llm=llm)
    initial: NbaAbsState = {
        "product": product,
        "ingredients": list(ingredients or []),
        "language": language,
        "jurisdiction": jurisdiction,
        "purpose": purpose,
        "entity_type": entity_type,
        "resource_source": resource_source,
    }
    if annual_turnover_inr is not None:
        initial["annual_turnover_inr"] = annual_turnover_inr
    if percentage_override is not None:
        initial["percentage_override"] = percentage_override
    if user_query:
        initial["user_query"] = user_query
    return app.invoke(initial)
