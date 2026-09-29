"""API tests for PDF upload (POST /api/v1/patent-advisor/extract) and document context."""

from __future__ import annotations

from fastapi.testclient import TestClient

import api.patent_advisor as patent_api
from config import get_settings
from graph.models import PatentDocumentFields, Section3Results
from graph.patent_advisor_graph import build_patent_advisor_graph
from graph.prompts import DOCUMENT_CONTEXT_HEADER
from main import app
from tests.conftest import ScriptedLLM
from tests.pdf_helpers import text_pdf
from websearch.mock import MockWebSearcher

client = TestClient(app)

DISCLOSURE = (
    "Invention: Ashwagandha capsule. Composition comprises Withania somnifera root "
    "extract and Tulsi leaf powder for stress relief."
)


def _upload(data: bytes, filename: str = "disclosure.pdf", content_type: str = "application/pdf"):
    return client.post(
        "/api/v1/patent-advisor/extract",
        files={"file": (filename, data, content_type)},
    )


def test_extract_returns_fields_and_text():
    seen: dict[str, str] = {}

    def _fields(user: str) -> PatentDocumentFields:
        seen["user"] = user
        return PatentDocumentFields(
            product="Ashwagandha capsule",
            ingredients=["Withania somnifera", " Tulsi ", ""],
            summary="Capsule for stress relief.",
        )

    patent_api._extract_llm = ScriptedLLM({"PatentDocumentFields": _fields})
    try:
        resp = _upload(text_pdf([DISCLOSURE]))
    finally:
        patent_api._extract_llm = None

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["filename"] == "disclosure.pdf"
    assert data["product"] == "Ashwagandha capsule"
    assert data["ingredients"] == ["Withania somnifera", "Tulsi"]
    assert data["total_pages"] == 1
    assert data["pages"][0]["method"] == "text"
    assert data["ocr_used"] is False
    assert "Withania somnifera" in data["document_text"]
    assert "Withania somnifera" in seen["user"]


def test_extract_rejects_non_pdf():
    resp = _upload(b"hello world", filename="notes.txt", content_type="text/plain")
    assert resp.status_code == 415

    resp = _upload(b"not a pdf at all", content_type="application/pdf")
    assert resp.status_code == 415


def test_extract_rejects_oversized(monkeypatch):
    small = get_settings().model_copy(update={"pdf_max_bytes": 100})
    monkeypatch.setattr(patent_api, "get_settings", lambda: small)
    resp = _upload(text_pdf([DISCLOSURE]))
    assert resp.status_code == 413


def test_extract_corrupt_pdf_is_400():
    resp = _upload(b"%PDF-1.4\ngarbage")
    assert resp.status_code == 400


def test_document_text_is_prompt_context_not_evidence():
    seen: dict[str, str] = {}
    default = ScriptedLLM()

    def _section3(user: str):
        seen["section3"] = user
        result = default(Section3Results, "", user)
        result.provisions[0].evidence_source_ids.append("uploaded-document")
        return result

    llm = ScriptedLLM({"Section3Results": _section3})
    patent_api._graph = build_patent_advisor_graph(llm=llm, searcher=MockWebSearcher())
    try:
        resp = client.post(
            "/api/v1/patent-advisor",
            json={
                "product": "Ashwagandha capsule",
                "ingredients": ["Ashwagandha"],
                "legal_scope": "domestic",
                "document_text": DISCLOSURE,
            },
        )
    finally:
        patent_api._graph = None

    assert resp.status_code == 200, resp.text
    assert DOCUMENT_CONTEXT_HEADER in seen["section3"]
    assert "Tulsi leaf powder" in seen["section3"]
    cited = {
        i for p in resp.json()["section3"]["provisions"] for i in p["evidence_source_ids"]
    }
    assert "uploaded-document" not in cited
