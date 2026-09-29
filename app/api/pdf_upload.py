"""Shared PDF upload handling for extract endpoints."""

from __future__ import annotations

import logging

from fastapi import HTTPException, UploadFile

from config import Settings, get_settings
from documents import PdfExtraction, extract_pdf_text
from graph.models import ProductDocumentExtractResponse, ProductDocumentFields, PdfPageInfo
from graph.prompts import PRODUCT_DOC_EXTRACT_SYSTEM
from llm import is_transient_llm_error
from llm.provider import get_chat_model
from llm.structured import structured_invoke

logger = logging.getLogger(__name__)

PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream"}

_extract_llm = None


def get_extract_llm():
    global _extract_llm
    if _extract_llm is None:
        _extract_llm = get_chat_model(settings=get_settings())
    return _extract_llm


def llm_http_error(exc: Exception) -> HTTPException:
    if is_transient_llm_error(exc):
        return HTTPException(
            status_code=503,
            detail="The LLM provider is temporarily overloaded. Please retry in a minute.",
        )
    return HTTPException(status_code=500, detail=str(exc))


def read_pdf_upload(file: UploadFile, settings: Settings) -> PdfExtraction:
    """Validate an uploaded PDF and extract its text (OCR for scanned pages)."""
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in PDF_CONTENT_TYPES:
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
        return extract_pdf_text(data, settings=settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def extract_product_document(file: UploadFile) -> ProductDocumentExtractResponse:
    """Extract text and product form fields from a product dossier / label PDF."""
    settings = get_settings()
    extraction = read_pdf_upload(file, settings)

    try:
        fields = structured_invoke(
            get_extract_llm(),
            ProductDocumentFields,
            system=PRODUCT_DOC_EXTRACT_SYSTEM,
            user=extraction.text[: settings.patent_doc_context_chars],
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("product document extract failed for file=%r", file.filename)
        raise llm_http_error(exc) from exc

    return ProductDocumentExtractResponse(
        filename=file.filename,
        product=fields.product.strip(),
        ingredients=[i.strip() for i in fields.ingredients if i and i.strip()],
        product_category=fields.product_category.strip(),
        summary=fields.summary.strip(),
        document_text=extraction.text,
        pages=[PdfPageInfo(**p.model_dump()) for p in extraction.pages],
        total_pages=extraction.total_pages,
        ocr_used=extraction.ocr_used,
        truncated=extraction.truncated,
    )
