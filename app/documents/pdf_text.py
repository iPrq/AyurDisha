"""Extract text from uploaded PDFs, falling back to local OCR for scanned pages."""

from __future__ import annotations

import io
import logging
import threading
from typing import Any, Literal

from pydantic import BaseModel, Field

from config import Settings, get_settings

logger = logging.getLogger(__name__)

PageMethod = Literal["text", "ocr", "empty"]


class PageText(BaseModel):
    page: int
    method: PageMethod
    chars: int


class PdfExtraction(BaseModel):
    text: str
    pages: list[PageText] = Field(default_factory=list)
    total_pages: int
    ocr_used: bool = False
    truncated: bool = False


_ocr_engine: Any | None = None
_ocr_lock = threading.Lock()


def _get_ocr_engine() -> Any:
    global _ocr_engine
    if _ocr_engine is None:
        with _ocr_lock:
            if _ocr_engine is None:
                from rapidocr import RapidOCR

                _ocr_engine = RapidOCR()
    return _ocr_engine


def _join_ocr_lines(boxes: Any, txts: Any) -> str:
    """Group OCR boxes into lines (top-to-bottom, left-to-right)."""
    items = []
    for box, txt in zip(boxes, txts):
        txt = (txt or "").strip()
        if not txt:
            continue
        ys = [float(p[1]) for p in box]
        xs = [float(p[0]) for p in box]
        items.append((min(ys), max(ys), min(xs), txt))
    if not items:
        return ""

    items.sort(key=lambda it: (it[0], it[2]))
    lines: list[list[tuple[float, float, float, str]]] = []
    for item in items:
        if lines:
            last = lines[-1]
            top = min(i[0] for i in last)
            bottom = max(i[1] for i in last)
            center = (item[0] + item[1]) / 2
            if top <= center <= bottom:
                last.append(item)
                continue
        lines.append([item])
    return "\n".join(
        " ".join(i[3] for i in sorted(line, key=lambda i: i[2])) for line in lines
    )


def _ocr_page(pdf: Any, index: int, dpi: int) -> str:
    import numpy as np

    page = pdf[index]
    try:
        bitmap = page.render(scale=dpi / 72)
        image = bitmap.to_pil().convert("RGB")
    finally:
        page.close()
    result = _get_ocr_engine()(np.array(image))
    if result is None or result.boxes is None or not result.txts:
        return ""
    return _join_ocr_lines(result.boxes, result.txts)


def extract_pdf_text(data: bytes, *, settings: Settings | None = None) -> PdfExtraction:
    """Per page: use the embedded text layer; OCR pages with too little text."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    cfg = settings or get_settings()
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported.")
        total_pages = len(reader.pages)
    except PdfReadError as exc:
        raise ValueError(f"Could not read PDF: {exc}") from exc
    if total_pages == 0:
        raise ValueError("PDF has no pages.")

    limit = min(total_pages, max(cfg.pdf_max_pages, 1))
    pdfium_doc = None
    pages: list[PageText] = []
    chunks: list[str] = []
    try:
        for i in range(limit):
            try:
                text = (reader.pages[i].extract_text() or "").strip()
            except Exception:  # noqa: BLE001
                logger.warning("text extraction failed on page %d", i + 1, exc_info=True)
                text = ""
            method: PageMethod = "text"

            if cfg.pdf_ocr_enabled and len(text) < cfg.pdf_ocr_min_chars:
                if pdfium_doc is None:
                    import pypdfium2 as pdfium

                    pdfium_doc = pdfium.PdfDocument(data)
                try:
                    ocr_text = _ocr_page(pdfium_doc, i, cfg.pdf_ocr_dpi).strip()
                except Exception:  # noqa: BLE001
                    logger.warning("OCR failed on page %d", i + 1, exc_info=True)
                    ocr_text = ""
                if len(ocr_text) > len(text):
                    text, method = ocr_text, "ocr"

            if not text:
                method = "empty"
            pages.append(PageText(page=i + 1, method=method, chars=len(text)))
            if text:
                chunks.append(f"[Page {i + 1}]\n{text}")
    finally:
        if pdfium_doc is not None:
            pdfium_doc.close()

    full_text = "\n\n".join(chunks)
    if not full_text.strip():
        raise ValueError("No text could be extracted from the PDF.")
    return PdfExtraction(
        text=full_text,
        pages=pages,
        total_pages=total_pages,
        ocr_used=any(p.method == "ocr" for p in pages),
        truncated=limit < total_pages,
    )
