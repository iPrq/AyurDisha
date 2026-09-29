"""Product Review FastAPI router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from api.patent_advisor import _to_legal_scope
from api.pdf_upload import extract_product_document
from config import get_settings
from graph.models import (
    ProductDocumentExtractResponse,
    ProductReviewRequest,
    ProductReviewResponse,
)
from graph.product_review_graph import build_product_review_graph
from knowledge_graph.factory import get_knowledge_graph
from knowledge_graph.service import record_response
from llm import is_transient_llm_error
from retrieval.factory import get_retriever
from websearch.factory import get_web_searcher

router = APIRouter(prefix="/api/v1", tags=["product-review"])

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        settings = get_settings()
        _graph = build_product_review_graph(
            retriever=get_retriever(settings),
            kg=get_knowledge_graph(settings),
            searcher=get_web_searcher(settings),
            settings=settings,
        )
    return _graph


def state_to_response(
    state: dict[str, Any], request: ProductReviewRequest
) -> ProductReviewResponse:
    return ProductReviewResponse(
        product=state.get("product") or request.product,
        ingredients=list(state.get("ingredients") or request.ingredients),
        language=state.get("language") or request.language,
        jurisdiction=state.get("jurisdiction") or request.jurisdiction,
        legal_scope=_to_legal_scope(state.get("legal_scope", request.legal_scope)),
        target_market=state.get("target_market") or request.target_market,
        botanicals=list(state.get("botanicals") or []),
        market_feasibility=state.get("market_feasibility"),
        legal_compliance=state.get("legal_compliance"),
        resource_accessibility=state.get("resource_accessibility"),
        combined_summary=state.get("combined_summary"),
        verification=state.get("verification"),
        retrieved_sources=list(state.get("retrieved_sources") or []),
        final_answer=state.get("final_answer"),
    )


@router.post("/product-review", response_model=ProductReviewResponse)
def product_review(
    request: ProductReviewRequest, background_tasks: BackgroundTasks
) -> ProductReviewResponse:
    """Market feasibility, legal compliance and resource accessibility (decision support)."""
    try:
        initial: dict[str, Any] = {
            "product": request.product,
            "ingredients": list(request.ingredients),
            "language": request.language,
            "jurisdiction": request.jurisdiction,
            "legal_scope": request.legal_scope,
        }
        if request.target_market:
            initial["target_market"] = request.target_market
        if request.product_category:
            initial["product_category"] = request.product_category
        if request.user_query:
            initial["user_query"] = request.user_query
        if request.document_text and request.document_text.strip():
            initial["document_text"] = request.document_text

        result = get_graph().invoke(initial)
        response = state_to_response(result, request)
        background_tasks.add_task(record_response, response, feature="product_review")
        return response
    except Exception as exc:  # noqa: BLE001
        if is_transient_llm_error(exc):
            raise HTTPException(
                status_code=503,
                detail="The LLM provider is temporarily overloaded. Please retry in a minute.",
            ) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/product-review/extract", response_model=ProductDocumentExtractResponse)
def product_review_extract(file: UploadFile = File(...)) -> ProductDocumentExtractResponse:
    """Extract text (with OCR for scanned pages) and form fields from a product document PDF."""
    return extract_product_document(file)
