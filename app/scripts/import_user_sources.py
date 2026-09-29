"""Import user-supplied source files from new_data/ into data/raw/sources/.

Run from app/:

    uv run python scripts/import_user_sources.py [--src new_data]

Same contract as scripts/fetch_sources.py:
- Originals are copied byte-for-byte (renamed to stable snake_case filenames).
- Writes a PROVENANCE.csv per source folder.
- Never writes *.meta.json sidecars, so nothing here is picked up by ingestion;
  scripts/build_corpus_docs.py derives the ingestible corpus documents.

Byte-identical duplicates in new_data/ (e.g. "TK Guidelines.pdf" ==
"Ayush Guidelines.pdf") are imported once; the duplicate name is recorded in notes.
Original download URLs were not supplied with the files; they are recorded only
where the document itself states them.
"""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import sys
from pathlib import Path

from fetch_sources import PROVENANCE_FIELDS, sha256_file, write_provenance

APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = APP_ROOT / "new_data"
DEFAULT_OUT = APP_ROOT / "data" / "raw" / "sources"
TODAY = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

USER_SUPPLIED = "user-supplied file (app/new_data); download URL not recorded"

# source_id -> list of files. sha256 pins the exact bytes that were reviewed.
SOURCES: dict[str, list[dict]] = {
    "cgpdtm_ayush_guidelines_2025": [{
        "original_filename": "Ayush Guidelines.pdf",
        "duplicates": ["TK Guidelines.pdf"],
        "stored_filename": "ayush_examination_guidelines_2025.pdf",
        "sha256": "2bab3cef1b08c07155976c089e05fc4f3f77009d4172423b145fc49da70ca082",
        "source_name": "CGPDTM - Guidelines for Examination of Ayush Related Inventions (2025)",
        "source_type": "guideline",
        "authority_level": "B",
        "jurisdiction": "india",
        "document_title": "Guidelines for Examination of Ayush Related Inventions",
        "original_source_url": "https://ipindia.gov.in (publisher site stated in the document; exact URL not recorded)",
        "license": "Government of India publication; reuse terms not verified",
        "notes": (
            "Office of the CGPDTM, DPIIT. 20 pages incl. cover pages listing granted Ayush patents. "
            "'TK Guidelines.pdf' in new_data is byte-identical and was not imported separately."
        ),
    }],
    "cgpdtm_pharma_guidelines_draft_2026": [{
        "original_filename": "pharma guide.pdf",
        "stored_filename": "pharma_examination_guidelines_draft_2026.pdf",
        "sha256": "bab2db739d3e837bf16c38d7e878ad20d7c5d92091fc0bf63885b1085e39b260",
        "source_name": "CGPDTM - DRAFT Guidelines for Examination of Patent Applications in the Field of Pharmaceuticals (2026)",
        "source_type": "guideline",
        "authority_level": "B (DRAFT - not final guidance)",
        "jurisdiction": "india",
        "document_title": "Draft Guidelines for Examination of Patent Applications in the Field of Pharmaceuticals 2026",
        "original_source_url": USER_SUPPLIED,
        "license": "Government of India publication; reuse terms not verified",
        "notes": "PDF title metadata: 'Pharmaceuticals Patent guidelines_CGPDTM_V4'. Marked 'Draft' on the cover.",
    }],
    "sc_novartis_v_uoi_2013": [{
        "original_filename": "Novartis_Ag_vs_Union_Of_India_Ors_on_1_April_2013.PDF",
        "stored_filename": "novartis_v_union_of_india_2013.pdf",
        "sha256": "fd7ce8e8cb919c20d5b2a2f7692d13dfb1b558a263b12ce41973ea16417d771b",
        "source_name": "Supreme Court of India - Novartis AG v. Union of India & Ors (1 April 2013)",
        "source_type": "case_law",
        "authority_level": "C (Indian Kanoon reproduction of the judgment)",
        "jurisdiction": "india",
        "document_title": "Novartis Ag vs Union Of India & Ors on 1 April, 2013",
        "original_source_url": "http://indiankanoon.org/doc/165776436/ (stated in the page footer)",
        "license": "Court judgment (public record); Indian Kanoon terms apply to the reproduction",
        "notes": "Civil Appeal Nos. 2706-2716 of 2013; (2013) 6 SCC 1. Leading authority on Section 3(d).",
    }],
    "ayurvedic_pharmacopoeia_india": [
        {
            "original_filename": "ayurveda medicines.pdf",
            "stored_filename": "api_part1_vol1.pdf",
            "sha256": "a255e935e29b16eae0012cdea435686686b0f4b1cfa8976905c3fc766af9c05a",
            "source_name": "The Ayurvedic Pharmacopoeia of India, Part I, Volume I (e-book)",
            "source_type": "prior_art",
            "authority_level": "B",
            "jurisdiction": "india",
            "document_title": "The Ayurvedic Pharmacopoeia of India, Part I, Volume I",
            "original_source_url": USER_SUPPLIED,
            "license": "Government of India publication; reuse terms not verified",
            "notes": (
                "Single-drug monographs (Govt. of India, Dept. of AYUSH). Text uses a legacy "
                "transliteration font; diacritics are restored during corpus build."
            ),
        },
        {
            "original_filename": "more formulations.pdf",
            "stored_filename": "api_part2_vol2.pdf",
            "sha256": "73bc7b7dbd2f659e6fd242a246710e4f3faa481704ff1b53d59ca0af5f0f1b82",
            "source_name": "The Ayurvedic Pharmacopoeia of India, Part II (Formulations), Volume II, First Edition (2008)",
            "source_type": "prior_art",
            "authority_level": "B",
            "jurisdiction": "india",
            "document_title": "The Ayurvedic Pharmacopoeia of India, Part II (Formulations), Volume II",
            "original_source_url": USER_SUPPLIED,
            "license": "Government of India publication (c) 2008 Ministry of Health and Family Welfare",
            "notes": (
                "States 'Effective from 1st January, 2009'. Mixes two legacy transliteration fonts "
                "and Kruti-Dev-encoded Sanskrit verses (verses dropped during corpus build)."
            ),
        },
    ],
    "ayurvedic_formulary_india": [{
        "original_filename": "forumaliton.pdf",
        "stored_filename": "afi_part1.pdf",
        "sha256": "1a8eb551798994c1f204ff3f110b4d7092d59c5c9d321e087fe0be08e84adfb2",
        "source_name": "The Ayurvedic Formulary of India, Part I, Second Revised Edition (e-book)",
        "source_type": "prior_art",
        "authority_level": "B",
        "jurisdiction": "india",
        "document_title": "The Ayurvedic Formulary of India, Part I",
        "original_source_url": USER_SUPPLIED,
        "license": "Government of India publication; reuse terms not verified",
        "notes": (
            "Classical compound formulations with source-text references. Sanskrit verses are in a "
            "legacy Devanagari font (dropped during corpus build); transliterations restored."
        ),
    }],
    "turmeric_patent_review_2021": [{
        "original_filename": "turmeric.pdf",
        "stored_filename": "turmeric_patent_case_review_2021.pdf",
        "sha256": "e773a3d86b2563b05c62d9bd90761d9831154916195eeaf91eb8ac575ca2f04b",
        "source_name": "Bhowmick, Deb Roy & De - A brief review on the turmeric patent case (NDC E-BIOS 1:83-88, 2021)",
        "source_type": "comparative_ip",
        "authority_level": "C (secondary: review article)",
        "jurisdiction": "us",
        "document_title": "A Brief Review on the Turmeric Patent Case with its Implications on the Documentation of Traditional Knowledge",
        "original_source_url": USER_SUPPLIED,
        "license": "Journal article; copyright of authors/publisher - reuse terms not verified",
        "notes": "ISSN 2583-6447. Discusses revocation of US turmeric wound-healing patent and TK documentation.",
    }],
    "lens_in_patents": [{
        "original_filename": "patent-data.csv",
        "stored_filename": "lens_in_patents_export.csv",
        "sha256": "dbe3a457ee3bf21e14b5803c3e79f83b9f865071576385d33ab0282d75664041",
        "source_name": "Lens.org patent export - Indian (IN) patent documents",
        "source_type": "patent_metadata",
        "authority_level": "C (Lens.org aggregation of patent office data)",
        "jurisdiction": "india",
        "document_title": "Lens.org export: 3001 IN patent documents (1752 applications, 1249 grants)",
        "original_source_url": "https://lens.org (per-record URLs in the URL column); search query not recorded",
        "license": "Lens.org export terms apply; underlying patent data is public record",
        "notes": (
            "Broad export: includes non-herbal subject matter (agrochemicals, energy, software). "
            "1398 rows have no abstract. No claims or full text in the export."
        ),
    }],
    "bhaishajya_kalpana_kosha": [{
        "original_filename": "Bhaishajya-Kalpana-Kosha.json",
        "stored_filename": "bhaishajya_kalpana_kosha.json",
        "sha256": "daa460151146108a2da149ef2c6201013732d60c84a3f910cdacefe301856664",
        "source_name": "Bhaishajya Kalpana Kosha",
        "source_type": "formulation_reference",
        "authority_level": "C (user-supplied compiled dataset; origin unknown; not an official pharmacopoeia)",
        "jurisdiction": "india",
        "document_title": "Bhaishajya Kalpana Kosha (176 formulations)",
        "original_source_url": USER_SUPPLIED,
        "license": "unknown - reuse terms not verified",
        "notes": "176 records. Clean JSON structure; 74 records have main ingredient mismatches, mostly distinct from AFI/API. Unknown origin.",
    }],
}

_FILE_KEYS = {"original_filename", "duplicates", "stored_filename", "sha256"}


def import_sources(src: Path, out: Path) -> list[str]:
    report: list[str] = []
    for source_id, files in SOURCES.items():
        folder = out / source_id
        folder.mkdir(parents=True, exist_ok=True)
        rows = []
        for spec in files:
            original = src / spec["original_filename"]
            if not original.is_file():
                raise FileNotFoundError(f"{original} not found")
            got = sha256_file(original)
            if got != spec["sha256"]:
                raise RuntimeError(
                    f"SHA-256 mismatch for {original.name}: expected {spec['sha256']}, got {got}"
                )
            for dup in spec.get("duplicates", []):
                if sha256_file(src / dup) != got:
                    raise RuntimeError(f"{dup} is not byte-identical to {original.name}")
            stored = folder / spec["stored_filename"]
            shutil.copyfile(original, stored)
            row = {k: v for k, v in spec.items() if k not in _FILE_KEYS}
            row.update(
                source_id=source_id,
                source_url=USER_SUPPLIED,
                retrieval_date_utc=TODAY,
                original_filename=spec["original_filename"],
                stored_filename=spec["stored_filename"],
                upstream_revision="",
                sha256=got,
                bytes=stored.stat().st_size,
            )
            assert set(row) <= set(PROVENANCE_FIELDS), set(row) - set(PROVENANCE_FIELDS)
            rows.append(row)
            report.append(f"[OK] {source_id}/{stored.name} ({row['bytes']:,} bytes, sha256 verified)")
        write_provenance(folder, rows)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    for line in import_sources(args.src, args.out):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
