"""PDF corpus cleanup: legacy-font glyph mapping, verse filtering, paragraph layout."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ingest.chunking import chunk_documents
from ingest.documents import load_raw_documents

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from pdf_corpus import (  # noqa: E402
    fix_legacy_iast,
    is_devanagari_verse,
    pharmacopoeia_text,
    reflow_prose,
    strip_page_furniture,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("A¿vagandh¡", "Aśvagandhā"),
        ("P¤¿nipar¸¢", "Pṛśniparṇī"),
        ("Gu·£c¢", "Guḍūcī"),
        ("AáVAGANDHË", "AŚVAGANDHĀ"),
        ("CÍRÛA", "CŪRṆA"),
        ("UraÅkÀata", "Uraḥkṣata"),
        ("Paµcasak¡ra", "Pañcasakāra"),
        ("á°dhana", "Śodhana"),
    ],
)
def test_font_a_glyphs(raw, expected):
    assert fix_legacy_iast(raw, "A") == expected


def test_font_a_keeps_units_and_degrees():
    assert fix_legacy_iast("10 µg/ml at 40°-60°", "A") == "10 µg/ml at 40°-60°"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("(Bhai¾ajyaratn¢val¤,", "(Bhaiṣajyaratnāvalī,"),
        ("Rasatara¬gi´ī", "Rasataraṅgiṇī"),
        ("ABHAY¡RI½¯A", "ABHAYĀRIṢṬA"),
        ("sa¼hitā", "saṃhitā"),
    ],
)
def test_font_b_words_detected_and_mapped(raw, expected):
    assert fix_legacy_iast(raw, "AB") == expected


def test_font_b_detection_leaves_font_a_words_alone():
    assert fix_legacy_iast("Dh¡tak¢ Vi·a´ga", "AB") == "Dhātakī Viḍaṅga"


@pytest.mark.parametrize(
    "line",
    [
        "+¦ÉªÉÉªÉÉºiÉÖ±ÉÉ¨ÉäEòÉÆ ¨ÉÞuùÒEòÉ%rÇùiÉÖ±ÉÉÆ iÉlÉÉ*",
        "foM³~xL; n'kiya e/kwddqleL; p AA 105 AA",
        "vÒ;k;kLrqykesdka e`}hdk·)Zrqyka rFkk A",
        'fuEcke`rko`"kiV¨yfufnfX/kdkuka',
    ],
)
def test_devanagari_verses_dropped(line):
    assert is_devanagari_verse(line, "AB")


@pytest.mark.parametrize(
    "line",
    [
        "Therapeutic uses: K¡sa (cough); áv¡sa (asthma); Ar¿a (piles);",
        "Dissolve 25 mg/ml in water (w/v)",
        "(Bhai¾ajyaratn¢val¤, Arºorog¢dhik¢ra ; 105-110)",
        "Dithizone;1,5-Diphenylthiocarbazone;Diphenylthiocarbazone",
    ],
)
def test_english_and_reference_lines_kept(line):
    assert not is_devanagari_verse(line, "AB")


def test_repeated_footer_and_page_numbers_removed():
    bodies = ["Alpha opens.", "Bravo follows.", "Charlie argues.", "Delta holds.", "Echo ends."]
    pages = [f"{b}\nIndian Kanoon - http://x/doc/1/ {i}\n{i}" for i, b in enumerate(bodies, 1)]
    assert strip_page_furniture(pages) == [[b] for b in bodies]


def test_repeated_labels_inside_page_body_are_kept():
    pages = [f"Title {c}\nintro {c}\nmore {c}\nDose\n3-6 g\nuse {c}\nend {c}\nlast {c}" for c in "abcde"]
    assert all("Dose" in lines for lines in strip_page_furniture(pages))


def test_reflow_joins_wrapped_lines_and_splits_numbered_paragraphs():
    long = "a wrapped sentence that runs on across the full width of the page and"
    pages = [[
        "Legal Provisions",
        f"1.1. The first {long}",
        "continues here.",
        f"1.2. The second {long} ends.",
    ]]
    paras = reflow_prose(pages).strip().split("\n\n")
    assert paras[0] == "Legal Provisions"
    assert paras[1] == f"1.1. The first {long} continues here."
    assert paras[2].startswith("1.2. The second")


def test_reflow_splits_oversized_paragraph_at_sentence_ends():
    sentence = "This placeholder sentence is exactly long enough to matter here. "
    text = reflow_prose([[(sentence * 60).strip()]])
    parts = text.strip().split("\n\n")
    assert len(parts) > 1
    assert all(len(p) <= 1500 and p.endswith(".") for p in parts)


def test_pharmacopoeia_titles_split_blocks_but_repeated_labels_do_not():
    pages = [
        ["AŚVAGANDHĀ", "SYNONYMS", "Sanskrit : Hayagandhā", "DOSE", "3-6 g"],
        ["ĀMALAKĪ", "SYNONYMS", "Sanskrit : Dhātrī", "DOSE", "3-6 g"],
        ["GUḌŪCĪ", "SYNONYMS", "Sanskrit : Amṛtā", "DOSE", "3-6 g"],
        ["HARĪTAKĪ", "SYNONYMS", "Sanskrit : Abhayā", "DOSE", "3-6 g"],
    ]
    blocks = pharmacopoeia_text(pages).strip().split("\n\n")
    assert blocks[0] == "AŚVAGANDHĀ"
    assert blocks[1].startswith("SYNONYMS\nSanskrit : Hayagandhā")
    assert len(blocks) == 8


def test_case_law_and_prior_art_use_paragraph_chunking(tmp_path):
    for doc_id, st in (("judgment", "case_law"), ("formulary", "prior_art")):
        (tmp_path / f"{doc_id}.md").write_text("HEADING\n\nFirst paragraph.\n", encoding="utf-8")
        (tmp_path / f"{doc_id}.meta.json").write_text(
            f'{{"doc_id": "{doc_id}", "title": "{doc_id}", "source_type": "{st}", '
            '"jurisdiction": "india", "legal_scope": "domestic"}',
            encoding="utf-8",
        )
    chunks = {c.id: c for c in chunk_documents(load_raw_documents(tmp_path))}
    assert chunks["judgment_p000"].source_type == "case_law"
    assert chunks["formulary_p000"].section == "HEADING"
