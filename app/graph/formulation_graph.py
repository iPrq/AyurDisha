"""LangGraph workflow: Formulation Intelligence (context → normalized → evidence-verified map).

parse_input → language_normalization → extract_formulation → resolve_botanicals → check_ambiguities
→ retrieve_context → characterize_formulation → build_structured_graph → verify_evidence → produce_actions
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from config import Settings, get_settings
from graph.formulation.characterize import characterize
from graph.formulation.clarify import formulation_missing_information, readiness
from graph.formulation.context_retrieval import retrieve_formulation_context
from graph.formulation.evidence import verify_graph
from graph.formulation.extraction import extract_formulation
from graph.formulation.graph_builder import build_graph
from graph.formulation.identity import resolve_ingredient
from graph.formulation.models import FormulationContext, FormulationIngredient, IdentityStatus
from graph.formulation.store import new_id
from graph.state import FormulationState
from knowledge_graph.base import BotanicalKnowledgeGraph
from language.base import LanguageProvider, LanguageServiceUnavailable
from language.fallback import FallbackLanguageProvider
from llm.provider import get_chat_model
from retrieval.base import LegalRetriever

logger = logging.getLogger(__name__)


def _ctx(state: FormulationState) -> FormulationContext:
    return state["formulation"].model_copy(deep=True)


def parse_input_node(state: FormulationState) -> dict[str, Any]:
    ctx = _ctx(state)
    raw = (state.get("raw_text") or "").strip()
    if raw and not ctx.original_user_text:
        ctx.original_user_text = raw
    return {"formulation": ctx, "raw_text": raw}


def language_normalization_node(state: FormulationState, *, provider: LanguageProvider) -> dict[str, Any]:
    raw = state.get("raw_text") or ""
    if not raw:
        return {"normalized_text": "", "language_method": "none"}
    requested = (state.get("language") or "auto").lower()
    detected = provider.detect_language(raw)
    source = detected.language if requested in ("", "auto") else requested
    ctx = _ctx(state)
    ctx.language = source
    if source == "en":
        return {"formulation": ctx, "normalized_text": raw, "language": "en", "language_method": detected.method}
    try:
        translated = provider.translate(raw, source_language=source, target_language="en")
        return {
            "formulation": ctx,
            "normalized_text": translated.text,
            "language": source,
            "language_method": f"{translated.provider}_translation",
        }
    except LanguageServiceUnavailable:
        # Keep the original text; extraction may still find canonical terms. Never pretend it was translated.
        return {
            "formulation": ctx,
            "normalized_text": raw,
            "language": source,
            "language_method": "untranslated",
            "escalation_reasons": ["translation_unavailable"],
        }


def extract_formulation_node(state: FormulationState, *, llm: Any | None, settings: Settings) -> dict[str, Any]:
    text = state.get("normalized_text") or ""
    if not text:
        return {"extraction_method": "none"}
    outcome = extract_formulation(text, llm=llm, max_chars=settings.patent_doc_context_chars)
    ex = outcome.extraction
    ctx = _ctx(state)
    for item in ex.ingredients:
        if ctx.find_ingredient(item.user_term) is not None:
            continue
        ctx.ingredients.append(
            FormulationIngredient(
                id=new_id("ing"),
                user_term=item.user_term.strip(),
                quantity=item.quantity,
                unit=item.unit,
                plant_part=item.plant_part,
                source_text=(item.source_text or "")[:200] or None,
            )
        )
    for field in ("name", "dosage_form", "route", "intended_use", "target_market"):
        value = getattr(ex, field)
        if value and not getattr(ctx, field):
            setattr(ctx, field, value.strip().lower() if field == "dosage_form" else value.strip())
    if ex.claims and not ctx.product_claims:
        ctx.product_claims = list(ex.claims)
    return {
        "formulation": ctx,
        "extraction_method": outcome.method,
        "extraction_dropped": outcome.dropped,
    }


def resolve_botanicals_node(
    state: FormulationState, *, kg: BotanicalKnowledgeGraph | None, settings: Settings, llm: Any | None
) -> dict[str, Any]:
    ctx = _ctx(state)
    for ing in ctx.ingredients:
        if ing.resolved_by_user or ing.botanical is not None:
            continue
        resolve_ingredient(ing, kg=kg, settings=settings, llm=llm)
    return {"formulation": ctx}


def check_ambiguities_node(state: FormulationState) -> dict[str, Any]:
    ctx = _ctx(state)
    ctx.missing_information = formulation_missing_information(ctx)
    reasons = []
    if any(i.identity_status == IdentityStatus.AMBIGUOUS for i in ctx.ingredients):
        reasons.append("ambiguous_botanical")
    return {"formulation": ctx, "escalation_reasons": reasons}


def retrieve_context_node(state: FormulationState, *, retriever: LegalRetriever | None) -> dict[str, Any]:
    pairs, empty = retrieve_formulation_context(state["formulation"], retriever=retriever)
    return {"source_pairs": pairs, "empty_branches": empty}


def characterize_node(state: FormulationState) -> dict[str, Any]:
    ctx = _ctx(state)
    ctx.formulation_characteristics = characterize(ctx)
    return {"formulation": ctx}


def build_structured_graph_node(state: FormulationState) -> dict[str, Any]:
    graph, claims = build_graph(
        state["formulation"], state.get("source_pairs") or [], empty_branches=state.get("empty_branches")
    )
    return {"graph": graph, "graph_claims": claims}


def verify_evidence_node(state: FormulationState, *, settings: Settings, llm: Any | None) -> dict[str, Any]:
    graph = verify_graph(
        state["graph"],
        state.get("graph_claims") or [],
        state.get("source_pairs") or [],
        settings=settings,
        llm=llm,
    )
    ctx = _ctx(state)
    ctx.evidence_ids = [e.source.id for e in graph.evidence if e.supports]
    return {"graph": graph, "formulation": ctx}


def produce_actions_node(state: FormulationState) -> dict[str, Any]:
    ctx = state["formulation"]
    actions: list[dict[str, Any]] = []
    for tool, label, action_type in (
        ("review", "Review Product", "RUN_PRODUCT_REVIEW"),
        ("patent", "Analyze Patent", "RUN_PATENT_ADVISOR"),
        ("nba-abs", "Check ABS", "RUN_ABS"),
    ):
        r = readiness(ctx, tool)  # type: ignore[arg-type]
        actions.append(
            {
                "tool": tool,
                "label": label,
                "action_type": action_type,
                "ready": r.ready,
                "missing": r.missing,
                "question": r.clarification.question if r.clarification else None,
            }
        )
    return {"suggested_actions": actions}


def build_formulation_graph(
    *,
    kg: BotanicalKnowledgeGraph | None = None,
    retriever: LegalRetriever | None = None,
    settings: Settings | None = None,
    llm: Any | None = None,
    language_provider: LanguageProvider | None = None,
):
    cfg = settings or get_settings()
    model = llm if llm is not None else get_chat_model(settings=cfg)
    provider = language_provider or FallbackLanguageProvider()

    graph = StateGraph(FormulationState)
    graph.add_node("parse_input", parse_input_node)
    graph.add_node("language_normalization", lambda s: language_normalization_node(s, provider=provider))
    graph.add_node("extract_formulation", lambda s: extract_formulation_node(s, llm=model, settings=cfg))
    graph.add_node(
        "resolve_botanicals", lambda s: resolve_botanicals_node(s, kg=kg, settings=cfg, llm=model)
    )
    graph.add_node("check_ambiguities", check_ambiguities_node)
    graph.add_node("retrieve_context", lambda s: retrieve_context_node(s, retriever=retriever))
    graph.add_node("characterize_formulation", characterize_node)
    graph.add_node("build_structured_graph", build_structured_graph_node)
    graph.add_node("verify_evidence", lambda s: verify_evidence_node(s, settings=cfg, llm=model))
    graph.add_node("produce_actions", produce_actions_node)

    order = [
        "parse_input",
        "language_normalization",
        "extract_formulation",
        "resolve_botanicals",
        "check_ambiguities",
        "retrieve_context",
        "characterize_formulation",
        "build_structured_graph",
        "verify_evidence",
        "produce_actions",
    ]
    graph.add_edge(START, order[0])
    for a, b in zip(order, order[1:]):
        graph.add_edge(a, b)
    graph.add_edge(order[-1], END)
    return graph.compile()
