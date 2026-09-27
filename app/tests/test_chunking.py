"""Document loading + legal-structure chunking."""

from __future__ import annotations

import json

import pytest

from graph.models import LegalScope
from ingest.chunking import chunk_documents
from ingest.documents import load_raw_documents


def _chunks(raw_dir):
    return {c.id: c for c in chunk_documents(load_raw_documents(raw_dir))}


def test_statute_clauses_are_whole_chunks(ingest_fixture_dir):
    chunks = _chunks(ingest_fixture_dir)
    d = chunks["fixture_patents_act_3_d"]
    assert d.section == "3(d)"
    assert d.source_type == "statute"
    # Explanation belongs to clause (d) and must not be split off
    assert "Explanation" in d.text
    assert "admixture" not in d.text
    assert chunks["fixture_patents_act_3_e"].section == "3(e)"
    assert "traditional knowledge" in chunks["fixture_patents_act_3_p"].text


def test_patent_abstract_and_first_claim(ingest_fixture_dir):
    chunks = _chunks(ingest_fixture_dir)
    abstract = chunks["patent_fixture_0001_a1_abstract"]
    claim = chunks["patent_fixture_0001_a1_claim_1"]
    assert abstract.source_type == "patent"
    assert abstract.section == "abstract"
    assert claim.section == "claim 1"
    assert "FIXTURE-0001-A1" in abstract.title


def test_guideline_preserves_heading_boundaries(ingest_fixture_dir):
    chunks = _chunks(ingest_fixture_dir)
    g0 = chunks["fixture_tk_guideline_p000"]
    g1 = chunks["fixture_tk_guideline_p001"]
    assert g0.section == "Traditional Knowledge Examination"
    assert g1.section == "Other IP Routes"
    assert "trademark" in g1.text
    assert "console.log" not in g0.text


def test_ids_are_deterministic(ingest_fixture_dir):
    first = [c.id for c in chunk_documents(load_raw_documents(ingest_fixture_dir))]
    second = [c.id for c in chunk_documents(load_raw_documents(ingest_fixture_dir))]
    assert first == second
    point_ids = [c.point_id for c in chunk_documents(load_raw_documents(ingest_fixture_dir))]
    assert point_ids == [
        c.point_id for c in chunk_documents(load_raw_documents(ingest_fixture_dir))
    ]


def test_metadata_attached(ingest_fixture_dir):
    chunks = _chunks(ingest_fixture_dir)
    intl = chunks["fixture_epo_comparative_p000"]
    assert intl.legal_scope == LegalScope.INTERNATIONAL
    assert intl.jurisdiction == "epo"
    assert all(c.is_fixture for c in chunks.values())


def test_file_without_sidecar_is_skipped(tmp_path):
    (tmp_path / "orphan.txt").write_text("3. Something.\n(a) text", encoding="utf-8")
    assert load_raw_documents(tmp_path) == []


def test_real_document_defaults_is_fixture_false(tmp_path):
    (tmp_path / "act.txt").write_text(
        "3. Heading.—\n(d) clause d text.\n(e) clause e text.", encoding="utf-8"
    )
    (tmp_path / "act.meta.json").write_text(
        json.dumps(
            {
                "doc_id": "sample_act",
                "title": "Sample Act",
                "source_type": "statute",
                "jurisdiction": "India",
                "legal_scope": "domestic",
            }
        ),
        encoding="utf-8",
    )
    chunks = chunk_documents(load_raw_documents(tmp_path))
    assert chunks and all(c.is_fixture is False for c in chunks)
    assert all(c.jurisdiction == "india" for c in chunks)


def test_duplicate_chunk_ids_rejected(tmp_path):
    for name in ("a", "b"):
        (tmp_path / f"{name}.txt").write_text("3. H.—\n(d) x.", encoding="utf-8")
        (tmp_path / f"{name}.meta.json").write_text(
            json.dumps(
                {
                    "doc_id": "same_doc",
                    "title": "T",
                    "source_type": "statute",
                    "jurisdiction": "india",
                    "legal_scope": "domestic",
                }
            ),
            encoding="utf-8",
        )
    with pytest.raises(ValueError, match="Duplicate chunk id"):
        chunk_documents(load_raw_documents(tmp_path))
