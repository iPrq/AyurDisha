"""Legal-structure-aware chunking with stable, deterministic chunk IDs."""

from __future__ import annotations

import logging
import re

from ingest.documents import DocumentMeta, PatentRecord, RawDocument
from retrieval.chunks import CanonicalChunk

logger = logging.getLogger(__name__)

GUIDELINE_MAX_CHARS = 1500

# Consolidated texts (e.g. India Code) prefix amended provisions with a footnote
# number and "[", e.g. "6[(d) the mere discovery ..." or "3[33A. Chapter not ...".
_FN_PREFIX = r"(?:\d+\[)?"
# "3. What are not inventions.—" / "3A." / "33EE. ..." at line start
# India Code writes section "33I" as "33-I" to avoid confusion with "331".
_SECTION_RE = re.compile(
    rf"^\s*{_FN_PREFIX}(\d{{1,3}}(?:-?[A-Z]{{1,3}})?)\.\s", re.MULTILINE
)
# "(d) the mere discovery ..." / "6[(d) ..." at line start
_CLAUSE_RE = re.compile(rf"^\s*{_FN_PREFIX}\(([a-z])\)\s", re.MULTILINE)
# Any line-start "(x)" / "(ii)" marker, used to look ahead for nested roman lists
_ANY_MARKER_RE = re.compile(rf"^\s*{_FN_PREFIX}\(([a-z]{{1,4}})\)\s", re.MULTILINE)

# --- Layout artifacts of PDF-derived consolidated texts (India Code style) ---
# Page-bottom amendment footnotes: "1. Ins. by Act 15 of 2005, s. 2 (w.e.f. 1-1-2005)."
_FOOTNOTE_RE = re.compile(
    r"^\s*\d+\.\s+(?:"
    r"(?:Ins|Subs|Rep|Omitted|Omit|Added|Renumbered|Inserted|Substituted)\b"
    r"|(?:The|Certain) words\b|The proviso\b|The Explanation\b"
    r"|Sub-sections?\b|Sub-clauses?\b|Clauses?\b|Chapter\b"
    r"|For (?:section|sub-section|clause|the)\b|Came into force\b|See\b|Vide\b"
    r"|\d{1,2}(?:st|nd|rd|th)\s+\w+,?\s+\d{4}"
    r"|.*\bw\.e\.f\."
    r")"
)
_PAGE_BREAK_RE = re.compile(r"^\s*(?:\d{1,4}\s+)?-{3,}\s*$")
_PAGE_NUMBER_RE = re.compile(r"^\s*\d{1,4}\s*$")
_RULE_LINE_RE = re.compile(r"^\s*_{3,}\s*$")
# Omitted provision left as a marker, e.g. "1*     -     -     -" (3(g) in India Code)
_OMISSION_LINE_RE = re.compile(r"^\s*\d*\*[\s\-.*]*$")
_CHAPTER_RE = re.compile(r"^\s*" + _FN_PREFIX + r"CHAPTER\s+[IVXLC]+[A-Z]?\]?\s*$")
_BODY_START_RE = re.compile(
    rf"^\s*(?:\*\*|{_FN_PREFIX}\((?:[a-z]{{1,4}}|\d{{1,3}}[A-Z]?)\)\s"
    rf"|{_FN_PREFIX}\d{{1,3}}(?:-?[A-Z]{{1,3}})?\.\s|{_FN_PREFIX}CHAPTER\b)"
)
_ROMAN_AMBIGUOUS = frozenset({"i", "v", "x"})
_ROMAN_CONTINUATIONS = frozenset({"ii", "iii", "iv", "vi", "vii", "viii", "ix", "xi"})
# Omission markers left in official texts for repealed clauses (after stripping
# digits/brackets/punctuation): "Omitted..." or only asterisks.
_OMITTED_RE = re.compile(r"^(?:omitted\w*|\*+$)", re.IGNORECASE)


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


def _strip_markdown(line: str) -> str:
    line = re.sub(r"^\s*#{1,6}\s+", "", line)
    line = line.replace("**", "")
    # italic delimiters: "_Explanation.—For ..._" -> "Explanation.—For ..."
    return re.sub(r"(?<![\w_])_(?=[^\s_])|(?<=[^\s_])_(?![\w_])", "", line)


def normalize_statute_text(text: str) -> tuple[str, list[str]]:
    """Remove layout artifacts from PDF/Markdown-derived statute text.

    Formatting only - statutory wording is never rewritten. Removed:
    Markdown emphasis/headings, page breaks and page numbers, rule lines,
    CHAPTER headings (and their all-caps title line), omission markers, and
    page-bottom amendment footnotes. Footnotes and omission markers are
    returned as ``notes`` so callers can log/preserve them.
    """
    out: list[str] = []
    notes: list[str] = []
    in_footnotes = False
    skip_chapter_title = False
    for raw in text.splitlines():
        body_start = bool(_BODY_START_RE.match(raw))
        line = _strip_markdown(raw)
        stripped = line.strip()
        if _PAGE_BREAK_RE.match(line) or _RULE_LINE_RE.match(raw):
            in_footnotes = False
            continue
        if _FOOTNOTE_RE.match(line) and not raw.lstrip().startswith("**"):
            in_footnotes = True
            notes.append(stripped)
            continue
        if in_footnotes:
            if not stripped or _PAGE_NUMBER_RE.match(line):
                continue
            if not body_start:
                notes[-1] = f"{notes[-1]} {stripped}"
                continue
            in_footnotes = False
        if _OMISSION_LINE_RE.match(line):
            notes.append(f"[omission marker] {stripped}")
            continue
        if _CHAPTER_RE.match(line):
            skip_chapter_title = True
            continue
        if skip_chapter_title:
            if not stripped:
                continue
            skip_chapter_title = False
            letters = re.sub(r"[^A-Za-z]", "", stripped)
            if letters and letters.isupper():
                continue
        out.append(line.rstrip())
    return "\n".join(out).strip(), notes


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


def _next_marker_is_roman_continuation(body: str, after: int) -> bool:
    """True if the next line-start "(..)" marker after ``after`` is (ii), (iii), ... ."""
    m = _ANY_MARKER_RE.search(body, after)
    return bool(m and m.group(1) in _ROMAN_CONTINUATIONS)


def _is_top_level_clause(m: re.Match[str], accepted: list[re.Match[str]], body: str) -> bool:
    letter = m.group(1)
    if accepted and letter <= accepted[-1].group(1):
        return False
    if letter not in _ROMAN_AMBIGUOUS:
        return True
    # "(i)", "(v)", "(x)" may be a nested roman numeral. Accept as a top-level clause
    # only if it is the next letter in the clause sequence (e.g. (i) directly after (h))
    # and is not immediately followed by a roman continuation such as (ii).
    if accepted and ord(letter) != ord(accepted[-1].group(1)) + 1:
        return False
    return not _next_marker_is_roman_continuation(body, m.end())


def _is_omitted(clause_text: str) -> bool:
    """Clause body is only an omission marker, e.g. "(g) [Omitted]" or "(g) * * *"."""
    rest = _CLAUSE_RE.sub("", clause_text, count=1)
    rest = re.sub(r"\d+|[\[\]().;,:\-—\s]", "", rest)
    return rest == "" or bool(_OMITTED_RE.match(rest))


def _split_clauses(body: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (preamble, [(letter, clause_text)]).

    A clause marker is accepted only if its letter is strictly after the previous
    clause letter; otherwise it is treated as part of the current clause (guards
    against nested (i)/(ii)-style enumerations re-starting the sequence). Roman-
    numeral-like letters are additionally checked against the expected sequence
    so a nested "(i)" inside e.g. clause (d) is not mistaken for clause (i).
    """
    accepted: list[re.Match[str]] = []
    for m in _CLAUSE_RE.finditer(body):
        if _is_top_level_clause(m, accepted, body):
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
    text, notes = normalize_statute_text(doc.text)
    if notes:
        logger.info(
            "%s: removed %d footnote/omission lines from chunk text", meta.doc_id, len(notes)
        )
    # Acts other than the Patents Act carry a label prefix (e.g. "BDA 3(a)") so their
    # sections are never mistaken for Patents Act Section 3 clauses.
    label = (lambda s: f"{meta.section_label_prefix} {s}") if meta.section_label_prefix else (lambda s: s)
    for sec, body in _split_sections(text, meta.section_prefix):
        preamble, clauses = _split_clauses(body)
        sec_slug = slugify(sec)
        if preamble:
            chunks.append(
                CanonicalChunk(
                    id=f"{meta.doc_id}_{sec_slug}",
                    title=f"{meta.title} — Section {label(sec)}",
                    text=preamble,
                    section=label(sec),
                    **_base_fields(meta),
                )
            )
        for letter, clause_text in clauses:
            if _is_omitted(clause_text):
                # Omitted clauses (e.g. 3(g)) never become active legal chunks.
                logger.warning(
                    "%s: Section %s(%s) is an omission marker in the source; no chunk emitted",
                    meta.doc_id,
                    sec,
                    letter,
                )
                continue
            chunks.append(
                CanonicalChunk(
                    id=f"{meta.doc_id}_{sec_slug}_{letter}",
                    title=f"{meta.title} — Section {label(f'{sec}({letter})')}",
                    text=clause_text,
                    section=label(f"{sec}({letter})"),
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
    if st in ("guideline", "comparative_ip", "regulation", "case_law", "prior_art"):
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
