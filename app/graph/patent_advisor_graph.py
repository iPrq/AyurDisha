"""LangGraph workflow: Section 3 & Patent Advisor (NVIDIA NIM nodes)."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from config import Settings, get_settings
from graph.patent_advisor.assemble import assemble_draft_answer
from graph.patent_advisor.ip_routes import ip_routes_node
from graph.patent_advisor.prior_art import prior_art_node
from graph.patent_advisor.retrieval import legal_patent_retrieval_node
from graph.patent_advisor.section3 import section3_scorer_node
from graph.shared.botanical import botanical_normalizer_node
from graph.shared.input_parser import input_parser_node
from graph.shared.verifier import critic_verifier_node
from graph.state import PatentAdvisorState
from knowledge_graph.base import BotanicalKnowledgeGraph
from llm.provider import get_chat_model
from retrieval.base import LegalRetriever


def build_patent_advisor_graph(
    *,
    kg: BotanicalKnowledgeGraph | None = None,
    retriever: LegalRetriever | None = None,
    settings: Settings | None = None,
    llm: Any | None = None,
):
    """Compile Patent Advisor StateGraph with NIM-backed reasoning nodes."""
    cfg = settings or get_settings()
    model = llm if llm is not None else get_chat_model(settings=cfg)

    def _botanical(state: PatentAdvisorState) -> dict[str, Any]:
        return botanical_normalizer_node(state, kg=kg, settings=cfg, llm=model)

    def _retrieval(state: PatentAdvisorState) -> dict[str, Any]:
        return legal_patent_retrieval_node(state, retriever=retriever, settings=cfg)

    def _section3(state: PatentAdvisorState) -> dict[str, Any]:
        return section3_scorer_node(state, settings=cfg, llm=model)

    def _prior_art(state: PatentAdvisorState) -> dict[str, Any]:
        return prior_art_node(state, llm=model)

    def _ip_routes(state: PatentAdvisorState) -> dict[str, Any]:
        return ip_routes_node(state, llm=model)

    def _verifier(state: PatentAdvisorState) -> dict[str, Any]:
        return critic_verifier_node(state, settings=cfg, llm=model)

    graph = StateGraph(PatentAdvisorState)
    graph.add_node("input_parser", input_parser_node)
    graph.add_node("botanical", _botanical)
    graph.add_node("retrieval", _retrieval)
    graph.add_node("section3", _section3)
    graph.add_node("prior_art", _prior_art)
    graph.add_node("ip_routes", _ip_routes)
    graph.add_node("assemble", assemble_draft_answer)
    graph.add_node("verifier", _verifier)

    graph.add_edge(START, "input_parser")
    graph.add_edge("input_parser", "botanical")
    graph.add_edge("botanical", "retrieval")
    graph.add_edge("retrieval", "section3")
    graph.add_edge("section3", "prior_art")
    graph.add_edge("prior_art", "ip_routes")
    graph.add_edge("ip_routes", "assemble")
    graph.add_edge("assemble", "verifier")
    graph.add_edge("verifier", END)

    return graph.compile()


def run_patent_advisor(
    *,
    product: str,
    ingredients: list[str] | None = None,
    language: str = "en",
    jurisdiction: str = "india",
    legal_scope: str = "domestic",
    user_query: str | None = None,
    document_text: str | None = None,
    kg: BotanicalKnowledgeGraph | None = None,
    retriever: LegalRetriever | None = None,
    settings: Settings | None = None,
    llm: Any | None = None,
) -> dict[str, Any]:
    """Invoke the Patent Advisor graph with a request payload."""
    app = build_patent_advisor_graph(
        kg=kg, retriever=retriever, settings=settings, llm=llm
    )
    initial: PatentAdvisorState = {
        "product": product,
        "ingredients": list(ingredients or []),
        "language": language,
        "jurisdiction": jurisdiction,
        "legal_scope": legal_scope,
    }
    if user_query:
        initial["user_query"] = user_query
    if document_text:
        initial["document_text"] = document_text
    return app.invoke(initial)
