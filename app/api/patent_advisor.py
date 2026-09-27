"""Patent Advisor FastAPI router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from config import get_settings
from graph.models import LegalScope, PatentAdvisorRequest, PatentAdvisorResponse
from graph.patent_advisor_graph import build_patent_advisor_graph
from knowledge_graph.factory import get_knowledge_graph
from retrieval.factory import get_retriever

router = APIRouter(prefix="/api/v1", tags=["patent-advisor"])

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        settings = get_settings()
        _graph = build_patent_advisor_graph(
            retriever=get_retriever(settings),
            kg=get_knowledge_graph(settings),
            settings=settings,
        )
    return _graph


def _to_legal_scope(value: Any) -> LegalScope:
    if isinstance(value, LegalScope):
        return value
    return LegalScope(str(value).lower())


def state_to_response(state: dict[str, Any], request: PatentAdvisorRequest) -> PatentAdvisorResponse:
    legal_scope = state.get("legal_scope", request.legal_scope)
    return PatentAdvisorResponse(
        product=state.get("product") or request.product,
        ingredients=list(state.get("ingredients") or request.ingredients),
        language=state.get("language") or request.language,
        jurisdiction=state.get("jurisdiction") or request.jurisdiction,
        legal_scope=_to_legal_scope(legal_scope),
        botanical=state.get("botanical"),
        section3=state.get("section3"),
        patentability_risk=state.get("patentability_risk"),
        prior_art=state.get("prior_art"),
        ip_routes=state.get("ip_routes"),
        verification=state.get("verification"),
        retrieved_sources=list(state.get("retrieved_sources") or []),
        final_answer=state.get("final_answer"),
    )


@router.post("/patent-advisor", response_model=PatentAdvisorResponse)
def patent_advisor(request: PatentAdvisorRequest) -> PatentAdvisorResponse:
    """Run Section 3 & Patent Advisor workflow (decision support, not legal advice)."""
    try:
        initial = {
            "product": request.product,
            "ingredients": list(request.ingredients),
            "language": request.language,
            "jurisdiction": request.jurisdiction,
            "legal_scope": request.legal_scope,
        }
        if request.user_query:
            initial["user_query"] = request.user_query

        result = get_graph().invoke(initial)
        return state_to_response(result, request)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
