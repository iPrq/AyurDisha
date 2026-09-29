"""PDF text extraction: text layer first, local RapidOCR for scanned pages."""

from __future__ import annotations

import pytest

from config import get_settings
from documents import extract_pdf_text
from tests.pdf_helpers import scanned_pdf, text_pdf


def _settings(**overrides):
    return get_settings().model_copy(update=overrides)


def test_text_layer_pdf_skips_ocr(monkeypatch):
    import documents.pdf_text as pdf_text

    def _no_ocr(*_args, **_kwargs):
        raise AssertionError("OCR should not run for pages with a text layer")

    monkeypatch.setattr(pdf_text, "_ocr_page", _no_ocr)
    line = "Herbal formulation comprising Withania somnifera root extract and Ocimum sanctum."
    result = extract_pdf_text(text_pdf([line, line]), settings=_settings())

    assert result.total_pages == 2
    assert [p.method for p in result.pages] == ["text", "text"]
    assert not result.ocr_used
    assert "Withania somnifera" in result.text
    assert "[Page 2]" in result.text


def test_scanned_pdf_uses_ocr():
    data = scanned_pdf(["Turmeric curcumin gel formulation", "Anti inflammatory topical use"])
    result = extract_pdf_text(data, settings=_settings())

    assert result.ocr_used
    assert result.pages[0].method == "ocr"
    text = result.text.lower()
    assert "turmeric" in text
    assert "curcumin" in text


def test_ocr_disabled_leaves_scanned_page_empty():
    data = scanned_pdf(["Turmeric curcumin gel formulation"])
    with pytest.raises(ValueError, match="No text"):
        extract_pdf_text(data, settings=_settings(pdf_ocr_enabled=False))


def test_page_cap_sets_truncated(monkeypatch):
    import documents.pdf_text as pdf_text

    monkeypatch.setattr(pdf_text, "_ocr_page", lambda *_a, **_k: "")
    line = "Ashwagandha capsule composition with standardized withanolides for stress relief."
    result = extract_pdf_text(text_pdf([line] * 5), settings=_settings(pdf_max_pages=2))

    assert result.total_pages == 5
    assert len(result.pages) == 2
    assert result.truncated


def test_corrupt_pdf_raises_value_error():
    with pytest.raises(ValueError):
        extract_pdf_text(b"%PDF-1.4\nnot really a pdf", settings=_settings())
