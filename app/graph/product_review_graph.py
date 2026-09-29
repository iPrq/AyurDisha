"""LangGraph workflow: Product Review (market / legal / resource run in parallel)."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from config import Settings, get_settings
from graph.product_review.aggregate import (
    collect_product_review_claims,
    product_review_aggregator_node,
)
from graph.product_review.legal import legal_compliance_node
from graph.product_review.market import market_feasibility_node
from graph.product_review.resource import resource_accessibility_node
from graph.shared.botanical import multi_botanical_normalizer_node
from graph.shared.input_parser import input_parser_node
from graph.shared.verifier import critic_verifier_node
from graph.state import ProductReviewState
from knowledge_graph.base import BotanicalKnowledgeGraph
from llm.provider import get_chat_model
from retrieval.base import LegalRetriever
from websearch.base import WebSearcher
from websearch.factory import get_web_searcher

DIMENSION_NODES = ("market_feasibility", "legal_compliance", "resource_accessibility")

PRODUCT_REVIEW_HUMAN_REVIEW_REASONS = frozenset(
    {
        "missing_market_evidence",
        "missing_regulatory_evidence",
        "missing_resource_evidence",
        "web_search_failed",
    }
)


def build_product_review_graph(
    *,
    kg: BotanicalKnowledgeGraph | None = None,
    retriever: LegalRetriever | None = None,
    searcher: WebSearcher | None = None,
    settings: Settings | None = None,
    llm: Any | None = None,
):
    cfg = settings or get_settings()
    model = llm if llm is not None else get_chat_model(settings=cfg)
    web = searcher if searcher is not None else get_web_searcher(cfg)

    def _botanical(state: ProductReviewState) -> dict[str, Any]:
        return multi_botanical_normalizer_node(state, kg=kg, settings=cfg, llm=model)

    def _market(state: ProductReviewState) -> dict[str, Any]:
        return market_feasibility_node(state, searcher=web, settings=cfg, llm=model)

    def _legal(state: ProductReviewState) -> dict[str, Any]:
        return legal_compliance_node(
            state, retriever=retriever, searcher=web, settings=cfg, llm=model
        )

    def _resource(state: ProductReviewState) -> dict[str, Any]:
        return resource_accessibility_node(state, searcher=web, settings=cfg, llm=model)

    def _verifier(state: ProductReviewState) -> dict[str, Any]:
        return critic_verifier_node(
            state,
            settings=cfg,
            llm=model,
            claims_collector=collect_product_review_claims,
            human_review_reasons=PRODUCT_REVIEW_HUMAN_REVIEW_REASONS,
        )

    graph = StateGraph(ProductReviewState)
    graph.add_node("input_parser", input_parser_node)
    graph.add_node("botanical", _botanical)
    graph.add_node("market_feasibility", _market)
    graph.add_node("legal_compliance", _legal)
    graph.add_node("resource_accessibility", _resource)
    graph.add_node("aggregate", product_review_aggregator_node)
    graph.add_node("verifier", _verifier)

    graph.add_edge(START, "input_parser")
    graph.add_edge("input_parser", "botanical")
    for node in DIMENSION_NODES:
        graph.add_edge("botanical", node)
    graph.add_edge(list(DIMENSION_NODES), "aggregate")
    graph.add_edge("aggregate", "verifier")
    graph.add_edge("verifier", END)

    return graph.compile()


def run_product_review(
    *,
    product: str,
    ingredients: list[str] | None = None,
    language: str = "en",
    jurisdiction: str = "india",
    legal_scope: str = "domestic",
    target_market: str | None = None,
    product_category: str | None = None,
    user_query: str | None = None,
    document_text: str | None = None,
    kg: BotanicalKnowledgeGraph | None = None,
    retriever: LegalRetriever | None = None,
    searcher: WebSearcher | None = None,
    settings: Settings | None = None,
    llm: Any | None = None,
) -> dict[str, Any]:
    app = build_product_review_graph(
        kg=kg, retriever=retriever, searcher=searcher, settings=settings, llm=llm
    )
    initial: ProductReviewState = {
        "product": product,
        "ingredients": list(ingredients or []),
        "language": language,
        "jurisdiction": jurisdiction,
        "legal_scope": legal_scope,
    }
    if target_market:
        initial["target_market"] = target_market
    if product_category:
        initial["product_category"] = product_category
    if user_query:
        initial["user_query"] = user_query
    if document_text:
        initial["document_text"] = document_text
    return app.invoke(initial)
