"""Legal-structure-aware chunking with stable, deterministic chunk IDs."""

from __future__ import annotations

import re

from ingest.documents import DocumentMeta, PatentRecord, RawDocument
from retrieval.chunks import CanonicalChunk

GUIDELINE_MAX_CHARS = 1500

# "3. What are not inventions.—" / "3A. ..." at line start
_SECTION_RE = re.compile(r"^\s*(\d{1,3}[A-Z]?)\.\s", re.MULTILINE)
# "(d) the mere discovery ..." at line start
_CLAUSE_RE = re.compile(r"^\s*\(([a-z])\)\s", re.MULTILINE)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _base_fields(meta: DocumentMeta) -> dict:
    return {
        "source_type": meta.source_type,
        "source_url": meta.source_url,
        "effective_date": meta.effective_date,
        "jurisdiction": meta.jurisdiction,
        "legal_scope": meta.legal_scope,
        "is_fixture": meta.is_fixture,
    }


# ---------------------------------------------------------------------------
# Statutes: one chunk per clause, e.g. 3(d), kept whole (incl. Explanations)
# ---------------------------------------------------------------------------


def _split_sections(text: str, default_section: str | None) -> list[tuple[str, str]]:
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        if not default_section:
            raise ValueError(
                "Statute text has no 'N.' section headings; set section_prefix in the sidecar."
            )
        return [(default_section, text)]
    out: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m.group(1), text[m.start() : end].strip()))
    return out


def _split_clauses(body: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (preamble, [(letter, clause_text)]).

    A clause marker is accepted only if its letter is strictly after the previous
    clause letter; otherwise it is treated as part of the current clause (guards
    against nested (i)/(ii)-style enumerations re-starting the sequence).
    """
    accepted: list[re.Match[str]] = []
    for m in _CLAUSE_RE.finditer(body):
        if not accepted or m.group(1) > accepted[-1].group(1):
            accepted.append(m)
    if not accepted:
        return body.strip(), []
    preamble = body[: accepted[0].start()].strip()
    clauses: list[tuple[str, str]] = []
    for i, m in enumerate(accepted):
        end = accepted[i + 1].start() if i + 1 < len(accepted) else len(body)
        clauses.append((m.group(1), body[m.start() : end].strip()))
    return preamble, clauses


def chunk_statute(doc: RawDocument) -> list[CanonicalChunk]:
    meta = doc.meta
    chunks: list[CanonicalChunk] = []
    for sec, body in _split_sections(doc.text, meta.section_prefix):
        preamble, clauses = _split_clauses(body)
        sec_slug = slugify(sec)
        if preamble:
            chunks.append(
                CanonicalChunk(
                    id=f"{meta.doc_id}_{sec_slug}",
                    title=f"{meta.title} — Section {sec}",
                    text=preamble,
                    section=sec,
                    **_base_fields(meta),
                )
            )
        for letter, clause_text in clauses:
            chunks.append(
                CanonicalChunk(
                    id=f"{meta.doc_id}_{sec_slug}_{letter}",
                    title=f"{meta.title} — Section {sec}({letter})",
                    text=clause_text,
                    section=f"{sec}({letter})",
                    **_base_fields(meta),
                )
            )
    return chunks


# ---------------------------------------------------------------------------
# Guidelines / comparative IP: paragraph + heading boundaries preserved
# ---------------------------------------------------------------------------


def _is_heading(paragraph: str) -> bool:
    return (
        "\n" not in paragraph
        and len(paragraph) <= 120
        and not paragraph.rstrip().endswith((".", ";", ":", ","))
    )


def chunk_guideline(doc: RawDocument, max_chars: int = GUIDELINE_MAX_CHARS) -> list[CanonicalChunk]:
    meta = doc.meta
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", doc.text) if p.strip()]

    groups: list[tuple[str | None, list[str]]] = []
    heading: str | None = None
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        if current:
            groups.append((heading, current))
            current = []

    for para in paragraphs:
        if _is_heading(para):
            flush()
            heading = para
            continue
        size = sum(len(p) for p in current) + len(para)
        if current and size > max_chars:
            flush()
        current.append(para)
    flush()

    chunks: list[CanonicalChunk] = []
    for idx, (head, paras) in enumerate(groups):
        text = "\n\n".join(paras)
        title = f"{meta.title} — {head}" if head else meta.title
        chunks.append(
            CanonicalChunk(
                id=f"{meta.doc_id}_p{idx:03d}",
                title=title,
                text=text,
                section=head,
                **_base_fields(meta),
            )
        )
    return chunks


# ---------------------------------------------------------------------------
# Patents: abstract + first claim, with patent metadata
# ---------------------------------------------------------------------------


def chunk_patent_record(meta: DocumentMeta, record: PatentRecord) -> list[CanonicalChunk]:
    pub = slugify(record.publication_number)
    fields = _base_fields(meta)
    fields.update(
        source_url=record.url or meta.source_url,
        effective_date=record.publication_date or meta.effective_date,
        jurisdiction=record.jurisdiction or meta.jurisdiction,
    )
    title = f"{record.title} ({record.publication_number})"
    chunks = [
        CanonicalChunk(
            id=f"patent_{pub}_abstract",
            title=title,
            text=record.abstract.strip(),
            section="abstract",
            **fields,
        )
    ]
    if record.first_claim and record.first_claim.strip():
        chunks.append(
            CanonicalChunk(
                id=f"patent_{pub}_claim_1",
                title=title,
                text=record.first_claim.strip(),
                section="claim 1",
                **fields,
            )
        )
    return chunks


def chunk_document(doc: RawDocument) -> list[CanonicalChunk]:
    st = doc.meta.source_type
    if st == "statute":
        return chunk_statute(doc)
    if st in ("guideline", "comparative_ip"):
        return chunk_guideline(doc)
    if st == "patent":
        out: list[CanonicalChunk] = []
        for record in doc.records:
            out.extend(chunk_patent_record(doc.meta, record))
        return out
    raise ValueError(f"Unsupported source_type {st!r}")


def chunk_documents(docs: list[RawDocument]) -> list[CanonicalChunk]:
    """Chunk all documents; duplicate chunk IDs are a hard error. Sorted by ID."""
    seen: dict[str, str] = {}
    chunks: list[CanonicalChunk] = []
    for doc in docs:
        for chunk in chunk_document(doc):
            if chunk.id in seen:
                raise ValueError(
                    f"Duplicate chunk id {chunk.id!r} from {doc.path} (also in {seen[chunk.id]})"
                )
            seen[chunk.id] = doc.path
            chunks.append(chunk)
    return sorted(chunks, key=lambda c: c.id)
