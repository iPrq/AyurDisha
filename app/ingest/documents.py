"""Raw document loading: sidecar metadata + PDF / HTML / text / patent JSON parsing."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from graph.models import LegalScope

logger = logging.getLogger(__name__)

SIDECAR_SUFFIX = ".meta.json"
TEXT_SUFFIXES = {".txt", ".md"}
HTML_SUFFIXES = {".html", ".htm"}
PDF_SUFFIXES = {".pdf"}
PATENT_SUFFIXES = {".json", ".jsonl"}

_DOC_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]*$")
_LABEL_PREFIX_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")


class DocumentMeta(BaseModel):
    """Sidecar metadata (``<file>.meta.json``). Required — metadata is never guessed."""

    doc_id: str
    title: str
    source_type: Literal["statute", "guideline", "patent", "comparative_ip", "regulation"]
    source_url: str | None = None
    effective_date: str | None = None
    jurisdiction: str
    legal_scope: LegalScope
    section_prefix: str | None = Field(
        default=None,
        description="Statutes: section number when the file holds a single section body",
    )
    section_label_prefix: str | None = Field(
        default=None,
        description=(
            "Statutes other than the Patents Act: short Act code prepended to every "
            "section label (e.g. 'BDA' -> 'BDA 3(a)') so their sections are never "
            "confused with Patents Act Section 3 clauses. Leave unset for the Patents Act."
        ),
    )
    is_fixture: bool = False

    @field_validator("section_label_prefix")
    @classmethod
    def _check_label_prefix(cls, v: str | None) -> str | None:
        if v is not None and not _LABEL_PREFIX_RE.match(v):
            raise ValueError(
                f"section_label_prefix {v!r} must be 2-10 uppercase letters/digits, starting with a letter"
            )
        return v

    @field_validator("doc_id")
    @classmethod
    def _check_doc_id(cls, v: str) -> str:
        if not _DOC_ID_RE.match(v):
            raise ValueError(
                f"doc_id {v!r} must be lowercase snake_case (a-z, 0-9, _)"
            )
        return v

    @field_validator("jurisdiction")
    @classmethod
    def _norm_jurisdiction(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("jurisdiction must not be empty")
        return v


class PatentRecord(BaseModel):
    publication_number: str
    title: str
    abstract: str
    first_claim: str | None = None
    url: str | None = None
    publication_date: str | None = None
    jurisdiction: str | None = None

    @field_validator("jurisdiction")
    @classmethod
    def _norm_jurisdiction(cls, v: str | None) -> str | None:
        return v.strip().lower() if v else v


class RawDocument(BaseModel):
    path: str
    meta: DocumentMeta
    text: str = ""
    records: list[PatentRecord] = Field(default_factory=list)


def _clean_lines(text: str) -> str:
    """Collapse intra-line whitespace, keep blank-line paragraph boundaries."""
    lines = [re.sub(r"[ \t\u00a0]+", " ", ln).strip() for ln in text.splitlines()]
    out: list[str] = []
    for ln in lines:
        if ln == "" and (not out or out[-1] == ""):
            continue
        out.append(ln)
    return "\n".join(out).strip()


def parse_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return _clean_lines("\n\n".join(pages))


def parse_html(path: Path) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    blocks = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"])
    if blocks:
        paras = [b.get_text(" ", strip=True) for b in blocks]
        return _clean_lines("\n\n".join(p for p in paras if p))
    return _clean_lines(soup.get_text("\n"))


def parse_text(path: Path) -> str:
    return _clean_lines(path.read_text(encoding="utf-8", errors="replace"))


def parse_patent_records(path: Path) -> list[PatentRecord]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        items = [json.loads(ln) for ln in raw.splitlines() if ln.strip()]
    else:
        data = json.loads(raw)
        items = data if isinstance(data, list) else [data]
    return [PatentRecord.model_validate(item) for item in items]


def sidecar_path(path: Path) -> Path:
    return path.with_name(path.stem + SIDECAR_SUFFIX)


def load_raw_documents(raw_dir: Path | str) -> list[RawDocument]:
    """Load every supported file with a sidecar under ``raw_dir`` (sorted, recursive)."""
    root = Path(raw_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Raw data directory not found: {root}")

    docs: list[RawDocument] = []
    supported = TEXT_SUFFIXES | HTML_SUFFIXES | PDF_SUFFIXES | PATENT_SUFFIXES
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.endswith(SIDECAR_SUFFIX):
            continue
        if path.name.startswith(".") or path.suffix.lower() not in supported:
            continue
        side = sidecar_path(path)
        if not side.exists():
            logger.warning(
                "Skipping %s: missing sidecar metadata %s", path.name, side.name
            )
            continue
        meta = DocumentMeta.model_validate_json(side.read_text(encoding="utf-8"))
        suffix = path.suffix.lower()
        if suffix in PATENT_SUFFIXES:
            if meta.source_type != "patent":
                raise ValueError(
                    f"{path.name}: JSON input is only supported for source_type=patent"
                )
            docs.append(
                RawDocument(path=str(path), meta=meta, records=parse_patent_records(path))
            )
            continue
        if suffix in PDF_SUFFIXES:
            text = parse_pdf(path)
        elif suffix in HTML_SUFFIXES:
            text = parse_html(path)
        else:
            text = parse_text(path)
        if not text.strip():
            logger.warning("Skipping %s: no extractable text", path.name)
            continue
        docs.append(RawDocument(path=str(path), meta=meta, text=text))

    logger.info("Loaded %d raw documents from %s", len(docs), root)
    return docs
