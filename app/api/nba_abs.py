"""NBA / ABS Calculator FastAPI router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from api.formulation_context import hydrate_from_formulation
from api.pdf_upload import extract_product_document
from api.streaming import SSE_HEADERS, stream_graph
from config import get_settings
from graph.models import NbaAbsRequest, NbaAbsResponse, ProductDocumentExtractResponse
from graph.nba_abs_graph import build_nba_abs_graph
from knowledge_graph.factory import get_knowledge_graph
from knowledge_graph.service import record_response
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


def build_initial(request: NbaAbsRequest) -> dict[str, Any]:
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
    if request.formulation_id:
        hydrate_from_formulation(initial, request.formulation_id, request.ingredients)
    return initial


@router.post("/nba-abs", response_model=NbaAbsResponse)
def nba_abs(request: NbaAbsRequest, background_tasks: BackgroundTasks) -> NbaAbsResponse:
    """ABS applicability + source-grounded rate + deterministic fee (decision support)."""
    initial = build_initial(request)
    try:
        result = get_graph().invoke(initial)
        response = state_to_response(result, request)
        background_tasks.add_task(record_response, response, feature="nba_abs")
        return response
    except Exception as exc:  # noqa: BLE001
        if is_transient_llm_error(exc):
            raise HTTPException(
                status_code=503,
                detail="The LLM provider is temporarily overloaded. Please retry in a minute.",
            ) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/nba-abs/stream")
def nba_abs_stream(request: NbaAbsRequest) -> StreamingResponse:
    """Same workflow as POST /nba-abs, streamed as SSE node-progress events."""
    initial = build_initial(request)
    return StreamingResponse(
        stream_graph(
            get_graph(),
            initial,
            workflow="nba_abs",
            to_response=lambda state: state_to_response(state, request),
            on_complete=lambda response: record_response(response, feature="nba_abs"),
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/nba-abs/extract", response_model=ProductDocumentExtractResponse)
def nba_abs_extract(file: UploadFile = File(...)) -> ProductDocumentExtractResponse:
    """Extract product name and ingredients from a product document PDF to pre-fill the form."""
    return extract_product_document(file)
