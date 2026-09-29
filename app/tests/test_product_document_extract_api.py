"""API tests for product document PDF upload (Product Review + NBA/ABS extract) and context."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api.pdf_upload as pdf_upload
import api.product_review as product_review_api
from config import get_settings
from graph.models import MarketFeasibilityAssessment, ProductDocumentFields
from graph.product_review_graph import build_product_review_graph
from graph.prompts import PRODUCT_DOCUMENT_CONTEXT_HEADER
from main import app
from tests.conftest import ScriptedLLM
from tests.pdf_helpers import text_pdf
from websearch.mock import MockWebSearcher

client = TestClient(app)

DOSSIER = (
    "Product: Brahmi memory tonic. Ayurvedic proprietary medicine. "
    "Each 10 ml contains Bacopa monnieri extract and Shankhpushpi."
)

EXTRACT_PATHS = ["/api/v1/product-review/extract", "/api/v1/nba-abs/extract"]


def _upload(
    path: str,
    data: bytes,
    filename: str = "dossier.pdf",
    content_type: str = "application/pdf",
):
    return client.post(path, files={"file": (filename, data, content_type)})


@pytest.mark.parametrize("path", EXTRACT_PATHS)
def test_extract_returns_product_fields(path):
    seen: dict[str, str] = {}

    def _fields(user: str) -> ProductDocumentFields:
        seen["user"] = user
        return ProductDocumentFields(
            product="Brahmi memory tonic",
            ingredients=["Bacopa monnieri", " Shankhpushpi ", ""],
            product_category=" Ayurvedic proprietary medicine ",
            summary="Syrup for memory support.",
        )

    pdf_upload._extract_llm = ScriptedLLM({"ProductDocumentFields": _fields})
    try:
        resp = _upload(path, text_pdf([DOSSIER]))
    finally:
        pdf_upload._extract_llm = None

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["filename"] == "dossier.pdf"
    assert data["product"] == "Brahmi memory tonic"
    assert data["ingredients"] == ["Bacopa monnieri", "Shankhpushpi"]
    assert data["product_category"] == "Ayurvedic proprietary medicine"
    assert data["total_pages"] == 1
    assert "Bacopa monnieri" in data["document_text"]
    assert "Bacopa monnieri" in seen["user"]


@pytest.mark.parametrize("path", EXTRACT_PATHS)
def test_extract_rejects_non_pdf(path):
    assert _upload(path, b"hello", filename="n.txt", content_type="text/plain").status_code == 415
    assert _upload(path, b"not a pdf at all").status_code == 415


@pytest.mark.parametrize("path", EXTRACT_PATHS)
def test_extract_rejects_oversized(path, monkeypatch):
    small = get_settings().model_copy(update={"pdf_max_bytes": 100})
    monkeypatch.setattr(pdf_upload, "get_settings", lambda: small)
    assert _upload(path, text_pdf([DOSSIER])).status_code == 413


@pytest.mark.parametrize("path", EXTRACT_PATHS)
def test_extract_corrupt_pdf_is_400(path):
    assert _upload(path, b"%PDF-1.4\ngarbage").status_code == 400


def test_product_review_document_text_is_prompt_context_not_evidence():
    seen: dict[str, str] = {}
    default = ScriptedLLM()

    def _market(user: str):
        seen["market"] = user
        result = default(MarketFeasibilityAssessment, "", user)
        result.findings[0].evidence_source_ids.append("uploaded-document")
        return result

    llm = ScriptedLLM({"MarketFeasibilityAssessment": _market})
    product_review_api._graph = build_product_review_graph(llm=llm, searcher=MockWebSearcher())
    try:
        resp = client.post(
            "/api/v1/product-review",
            json={
                "product": "Brahmi memory tonic",
                "ingredients": ["Brahmi"],
                "legal_scope": "domestic",
                "document_text": DOSSIER,
            },
        )
    finally:
        product_review_api._graph = None

    assert resp.status_code == 200, resp.text
    assert PRODUCT_DOCUMENT_CONTEXT_HEADER in seen["market"]
    assert "Shankhpushpi" in seen["market"]
    cited = {
        i for f in resp.json()["market_feasibility"]["findings"] for i in f["evidence_source_ids"]
    }
    assert "uploaded-document" not in cited
