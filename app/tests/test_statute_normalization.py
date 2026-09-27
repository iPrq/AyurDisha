"""Statute chunking on PDF/Markdown-derived consolidated texts (India Code layout).

Synthetic cases use PLACEHOLDER wording that only mimics the layout; no statutory
text is reproduced. The last test runs against the real corpus if it has been built
(data/raw/corpus/, created by scripts/build_corpus_docs.py) and is skipped otherwise.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from graph.models import SUPPORTED_SECTION3_CLAUSES
from ingest.chunking import chunk_documents, normalize_statute_text
from ingest.documents import load_raw_documents

INDIACODE_STYLE = """\
**3. Placeholder heading.—The following are placeholder items within the meaning of this**

Act,—

(a) placeholder alpha wraps onto a

continuation line;

4[(b) placeholder bravo inserted by amendment;]

6[(d) placeholder delta body.

_Explanation.—Placeholder explanation text for delta_

wraps here;]

1. Ins. by Act 1 of 2000, s. 2 (w.e.f. 1-1-2000).
2. Subs. by s. 3, ibid., for “old words”
(w.e.f. 1-1-2000).
4. Subs. by Act 2 of 2001, s. 4, for clause (b) (w.e.f. 2-2-2001).

12

-----

(e) placeholder echo body;

(f) placeholder foxtrot body;

1*     -     -     -
(h) placeholder hotel body;

**4. Next placeholder heading.—Placeholder body.**

2[CHAPTER IVA

PROVISIONS RELATING TO [3][PLACEHOLDER] ITEMS

**33H. Placeholder section.—Body text.**

2[33-I. Hyphenated placeholder section.—Body text.

(1) placeholder sub-section;
"""


def _write(tmp_path: Path, text: str) -> Path:
    (tmp_path / "act.md").write_text(text, encoding="utf-8")
    (tmp_path / "act.meta.json").write_text(
        json.dumps(
            {
                "doc_id": "t",
                "title": "T",
                "source_type": "statute",
                "jurisdiction": "india",
                "legal_scope": "domestic",
                "is_fixture": True,
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def chunks(tmp_path):
    return {c.id: c for c in chunk_documents(load_raw_documents(_write(tmp_path, INDIACODE_STYLE)))}


def test_bold_headings_and_hyphenated_sections_detected(chunks):
    sections = {c.section for c in chunks.values()}
    assert {"3", "4", "33H", "33-I"} <= sections
    assert "t_33_i" in chunks


def test_footnote_prefixed_clause_markers_detected(chunks):
    assert chunks["t_3_b"].section == "3(b)"
    assert chunks["t_3_b"].text.startswith("4[(b)")
    assert chunks["t_3_d"].section == "3(d)"


def test_footnotes_are_not_sections_and_not_in_clause_text(chunks):
    assert not any(c.section in {"1", "2"} for c in chunks.values())
    for c in chunks.values():
        assert "Ins. by" not in c.text and "Subs. by" not in c.text
        assert "w.e.f." not in c.text  # includes the wrapped "(w.e.f. ...)." continuation
        assert "-----" not in c.text and "**" not in c.text


def test_explanation_stays_with_its_clause_and_italics_stripped(chunks):
    d = chunks["t_3_d"].text
    assert "Explanation.—Placeholder explanation" in d and "_" not in d
    assert "echo" not in d


def test_omission_marker_creates_no_clause_and_is_not_absorbed(chunks):
    assert not any(c.section == "3(g)" for c in chunks.values())
    assert "*" not in chunks["t_3_f"].text
    assert chunks["t_3_h"].section == "3(h)"


def test_chapter_heading_and_title_removed(chunks):
    four = chunks["t_4"].text
    assert "CHAPTER" not in four and "PROVISIONS RELATING TO" not in four


def test_notes_are_returned_not_lost():
    _, notes = normalize_statute_text(INDIACODE_STYLE)
    assert any(n.startswith("1. Ins. by") for n in notes)
    assert any("(w.e.f. 1-1-2000)." in n and n.startswith("2. Subs.") for n in notes)
    assert any(n.startswith("[omission marker]") for n in notes)


def test_plain_text_statute_unaffected():
    text = "3. H.—pre\n(d) clause d.\nExplanation.—kept.\n(e) clause e."
    norm, notes = normalize_statute_text(text)
    assert norm == text and notes == []


CORPUS = Path(__file__).resolve().parents[1] / "data" / "raw" / "corpus"


@pytest.mark.skipif(
    not (CORPUS / "hf_patents_act_1970_s3.meta.json").exists(),
    reason="real corpus not built (run scripts/build_corpus_docs.py)",
)
def test_real_patents_act_section3_has_exactly_15_clauses():
    docs = [d for d in load_raw_documents(CORPUS) if d.meta.doc_id == "hf_patents_act_1970_s3"]
    chunks = chunk_documents(docs)
    clause_sections = [c.section for c in chunks if c.section != "3"]
    assert clause_sections == list(SUPPORTED_SECTION3_CLAUSES)
    assert "3(g)" not in clause_sections
    assert all(c.is_fixture is False for c in chunks)
