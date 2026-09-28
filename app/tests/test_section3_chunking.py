"""Section 3 chunking: 15 clause chunks, nested (i)/(ii) handling, omitted 3(g).

Uses placeholder text only — no statutory wording is reproduced in fixtures.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from graph.models import SUPPORTED_SECTION3_CLAUSES
from ingest.chunking import _split_clauses, chunk_documents
from ingest.documents import load_raw_documents

PLACEHOLDER_DIR = Path(__file__).resolve().parent / "fixtures" / "section3_placeholder"


def _chunks(raw_dir):
    return {c.id: c for c in chunk_documents(load_raw_documents(raw_dir))}


def _write_statute(tmp_path, text: str, doc_id: str = "t_act") -> Path:
    (tmp_path / "act.txt").write_text(text, encoding="utf-8")
    (tmp_path / "act.meta.json").write_text(
        json.dumps(
            {
                "doc_id": doc_id,
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


def test_full_structure_produces_fifteen_clause_chunks():
    chunks = _chunks(PLACEHOLDER_DIR)
    sections = sorted(c.section for c in chunks.values() if c.section.startswith("3("))
    assert sections == sorted(SUPPORTED_SECTION3_CLAUSES)
    assert "fixture_s3_placeholder_3" in chunks  # preamble
    assert "fixture_s3_placeholder_4" in chunks  # next section still split off
    for ref in SUPPORTED_SECTION3_CLAUSES:
        letter = ref[2]
        c = chunks[f"fixture_s3_placeholder_3_{letter}"]
        assert c.section == ref
        assert c.text.startswith(f"({letter})")


def test_no_active_3g_chunk(caplog):
    with caplog.at_level(logging.WARNING, logger="ingest.chunking"):
        chunks = _chunks(PLACEHOLDER_DIR)
    assert "fixture_s3_placeholder_3_g" not in chunks
    assert not any(c.section == "3(g)" for c in chunks.values())
    # (f) must not swallow the omission marker
    assert "Omitted" not in chunks["fixture_s3_placeholder_3_f"].text
    assert any("3(g)" in r.getMessage() for r in caplog.records)


def test_nested_roman_list_stays_inside_parent_clause():
    chunks = _chunks(PLACEHOLDER_DIR)
    d = chunks["fixture_s3_placeholder_3_d"].text
    assert "nested delta item one" in d and "nested delta item two" in d
    assert "echo" not in d
    k = chunks["fixture_s3_placeholder_3_k"].text
    assert "nested kilo item two" in k and "lima" not in k
    i = chunks["fixture_s3_placeholder_3_i"].text
    assert "india" in i and "nested" not in i


def test_nested_i_before_clause_i_does_not_swallow_later_clauses():
    body = (
        "3. H.—pre\n(d) clause d text:\n(i) nested one;\n(ii) nested two.\n"
        "(e) clause e text.\n(f) clause f text."
    )
    _, clauses = _split_clauses(body)
    assert [letter for letter, _ in clauses] == ["d", "e", "f"]
    assert "nested two" in clauses[0][1]


def test_single_nested_i_without_ii_is_not_top_level_out_of_sequence():
    body = "3. H.—pre\n(d) clause d:\n(i) lone nested item.\n(e) clause e."
    _, clauses = _split_clauses(body)
    assert [letter for letter, _ in clauses] == ["d", "e"]


def test_top_level_i_after_h_is_accepted():
    body = "3. H.—pre\n(h) clause h.\n(i) clause i.\n(j) clause j."
    _, clauses = _split_clauses(body)
    assert [letter for letter, _ in clauses] == ["h", "i", "j"]


def test_existing_d_e_p_sequence_unchanged(ingest_fixture_dir):
    chunks = _chunks(ingest_fixture_dir)
    ids = sorted(k for k in chunks if k.startswith("fixture_patents_act_"))
    assert ids == [
        "fixture_patents_act_3",
        "fixture_patents_act_3_d",
        "fixture_patents_act_3_e",
        "fixture_patents_act_3_p",
    ]


@pytest.mark.parametrize(
    "marker",
    ["(g) [Omitted]", "(g) * * * * *", "(g) 1[* * *]", "(g) [Omitted by Act 1 of 2000, s. 2.]"],
)
def test_omission_marker_variants_skipped(tmp_path, marker):
    raw = _write_statute(tmp_path, f"3. H.—pre\n(f) clause f.\n{marker}\n(h) clause h.")
    chunks = _chunks(raw)
    assert "t_act_3_g" not in chunks
    assert {"t_act_3_f", "t_act_3_h"} <= set(chunks)


def test_real_clause_text_is_not_treated_as_omitted(tmp_path):
    raw = _write_statute(tmp_path, "3. H.—pre\n(f) clause f.\n(g) a real clause body.\n")
    assert "t_act_3_g" in _chunks(raw)
