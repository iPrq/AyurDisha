"""Patent Advisor FastAPI router."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from config import get_settings
from documents import extract_pdf_text
from graph.models import (
    LegalScope,
    PatentAdvisorRequest,
    PatentAdvisorResponse,
    PatentDocumentExtractResponse,
    PatentDocumentFields,
    PdfPageInfo,
)
from graph.patent_advisor_graph import build_patent_advisor_graph
from graph.prompts import PATENT_DOC_EXTRACT_SYSTEM
from knowledge_graph.factory import get_knowledge_graph
from llm import is_transient_llm_error
from llm.provider import get_chat_model
from llm.structured import structured_invoke
from retrieval.factory import get_retriever

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["patent-advisor"])

_graph = None
_extract_llm = None

_PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream"}


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


def get_extract_llm():
    global _extract_llm
    if _extract_llm is None:
        _extract_llm = get_chat_model(settings=get_settings())
    return _extract_llm


def _to_legal_scope(value: Any) -> LegalScope:
    if isinstance(value, LegalScope):
        return value
    return LegalScope(str(value).lower())


def _llm_http_error(exc: Exception) -> HTTPException:
    if is_transient_llm_error(exc):
        return HTTPException(
            status_code=503,
            detail="The LLM provider is temporarily overloaded. Please retry in a minute.",
        )
    return HTTPException(status_code=500, detail=str(exc))


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
        if request.document_text and request.document_text.strip():
            initial["document_text"] = request.document_text

        result = get_graph().invoke(initial)
        return state_to_response(result, request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("patent-advisor failed for product=%r", request.product)
        raise _llm_http_error(exc) from exc


@router.post("/patent-advisor/extract", response_model=PatentDocumentExtractResponse)
def patent_advisor_extract(file: UploadFile = File(...)) -> PatentDocumentExtractResponse:
    """Extract text (with OCR for scanned pages) and form fields from a disclosure PDF."""
    settings = get_settings()
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in _PDF_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Only PDF files are supported.")

    data = file.file.read(settings.pdf_max_bytes + 1)
    if len(data) > settings.pdf_max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"PDF exceeds the {settings.pdf_max_bytes // (1024 * 1024)} MB limit.",
        )
    if not data.lstrip()[:5].startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="File is not a valid PDF.")

    try:
        extraction = extract_pdf_text(data, settings=settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        fields = structured_invoke(
            get_extract_llm(),
            PatentDocumentFields,
            system=PATENT_DOC_EXTRACT_SYSTEM,
            user=extraction.text[: settings.patent_doc_context_chars],
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("patent-advisor extract failed for file=%r", file.filename)
        raise _llm_http_error(exc) from exc

    return PatentDocumentExtractResponse(
        filename=file.filename,
        product=fields.product.strip(),
        ingredients=[i.strip() for i in fields.ingredients if i and i.strip()],
        summary=fields.summary.strip(),
        document_text=extraction.text,
        pages=[PdfPageInfo(**p.model_dump()) for p in extraction.pages],
        total_pages=extraction.total_pages,
        ocr_used=extraction.ocr_used,
        truncated=extraction.truncated,
    )
