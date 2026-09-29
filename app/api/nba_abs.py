"""NBA / ABS Calculator FastAPI router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.pdf_upload import extract_product_document
from config import get_settings
from graph.models import NbaAbsRequest, NbaAbsResponse, ProductDocumentExtractResponse
from graph.nba_abs_graph import build_nba_abs_graph
from knowledge_graph.factory import get_knowledge_graph
from llm import is_transient_llm_error
from retrieval.factory import get_retriever

router = APIRouter(prefix="/api/v1", tags=["nba-abs"])

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        settings = get_settings()
        _graph = build_nba_abs_graph(
            retriever=get_retriever(settings),
            kg=get_knowledge_graph(settings),
            settings=settings,
        )
    return _graph


def state_to_response(state: dict[str, Any], request: NbaAbsRequest) -> NbaAbsResponse:
    return NbaAbsResponse(
        product=state.get("product") or request.product,
        ingredients=list(state.get("ingredients") or request.ingredients),
        jurisdiction=state.get("jurisdiction") or request.jurisdiction,
        purpose=request.purpose,
        entity_type=request.entity_type,
        resource_source=request.resource_source,
        annual_turnover_inr=request.annual_turnover_inr,
        botanicals=list(state.get("botanicals") or []),
        applicability=state.get("applicability"),
        rate_selection=state.get("rate_selection"),
        calculation=state.get("calculation"),
        verification=state.get("verification"),
        retrieved_sources=list(state.get("retrieved_sources") or []),
        final_answer=state.get("final_answer"),
    )


@router.post("/nba-abs", response_model=NbaAbsResponse)
def nba_abs(request: NbaAbsRequest) -> NbaAbsResponse:
    """ABS applicability + source-grounded rate + deterministic fee (decision support)."""
    try:
        initial: dict[str, Any] = {
            "product": request.product,
            "ingredients": list(request.ingredients),
            "language": request.language,
            "jurisdiction": request.jurisdiction,
            "purpose": request.purpose,
            "entity_type": request.entity_type,
            "resource_source": request.resource_source,
        }
        if request.annual_turnover_inr is not None:
            initial["annual_turnover_inr"] = request.annual_turnover_inr
        if request.percentage_override is not None:
            initial["percentage_override"] = request.percentage_override
        if request.user_query:
            initial["user_query"] = request.user_query

        result = get_graph().invoke(initial)
        return state_to_response(result, request)
    except Exception as exc:  # noqa: BLE001
        if is_transient_llm_error(exc):
            raise HTTPException(
                status_code=503,
                detail="The LLM provider is temporarily overloaded. Please retry in a minute.",
            ) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/nba-abs/extract", response_model=ProductDocumentExtractResponse)
def nba_abs_extract(file: UploadFile = File(...)) -> ProductDocumentExtractResponse:
    """Extract product name and ingredients from a product document PDF to pre-fill the form."""
    return extract_product_document(file)
