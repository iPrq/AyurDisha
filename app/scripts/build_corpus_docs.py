"""Build ingestible corpus documents (layer B) from fetched source files (layer A).

Run from app/ after scripts/fetch_sources.py:

    uv run python scripts/build_corpus_docs.py

Reads   data/raw/sources/hf_indian_legal_acts/*.md          (verbatim Act text)
        data/raw/sources/hupd_sample_subset/*.jsonl        (US patent applications)
        data/raw/sources/<user source>/*.pdf|csv           (scripts/import_user_sources.py)
Writes  data/raw/corpus/<doc_id>.(md|json) + <doc_id>.meta.json + CORPUS_PROVENANCE.csv

Each Act document is a VERBATIM excerpt of the source text, cut at fixed
anchors (no rewording). Layout artifacts (Markdown, page footnotes, page breaks)
are handled later by the statute chunker, not here. Fails loudly if an anchor
is missing rather than guessing. Does not index anything.

PDF sources are converted with formatting-only cleanup (see scripts/pdf_corpus.py);
that step dominates the run time (a few minutes for ~1,500 pages).
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from pdf_corpus import (
    clean_pharmacopoeia_pages,
    extract_pages,
    pharmacopoeia_text,
    reflow_prose,
    strip_page_furniture,
)

APP_ROOT = Path(__file__).resolve().parents[1]
SRC = APP_ROOT / "data" / "raw" / "sources" / "hf_indian_legal_acts"
OUT = APP_ROOT / "data" / "raw" / "corpus"
HF_URL = "https://huggingface.co/datasets/geekyrakshit/indian-legal-acts"
TODAY = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

# start/end are regexes matched against whole lines; end=None means end of file.
EXTRACTS = [
    {
        "doc_id": "hf_patents_act_1970_s3",
        "source_file": "patents_act_1970.md",
        "title": "The Patents Act, 1970 (via HF indian-legal-acts)",
        "start": r"^\*\*3\. What are not inventions",
        "end": r"^\*\*4\. Inventions relating to atomic energy",
        "scope": "Section 3 only",
    },
    {
        "doc_id": "hf_biological_diversity_act_2002",
        "source_file": "biological_diversity_act_2002.md",
        "title": "The Biological Diversity Act, 2002 (via HF indian-legal-acts)",
        "start": r"^\s*(?:#+\s*)?An Act to",
        "end": None,
        "scope": "Act body (arrangement-of-sections table excluded)",
        "section_label_prefix": "BDA",
    },
    {
        "doc_id": "hf_drugs_and_cosmetics_act_1940_ch4a",
        "source_file": "drugs_and_cosmetics_act_1940.md",
        "title": "The Drugs and Cosmetics Act, 1940 (via HF indian-legal-acts)",
        "after": r"^\s*(?:#+\s*)?An Act to",  # skip the arrangement-of-sections table
        "start": r"^\s*(?:\d+\[)?33A\. Chapter not to apply to Ayurvedic",
        "end": r"^\s*(?:\d+\[)?CHAPTER V\s*$",
        "scope": "Section 33A and Chapter IVA (Ayurvedic, Siddha and Unani drugs), up to Chapter V",
        "section_label_prefix": "DCA",
    },
]


def _matches_sha256(data: bytes, expected: str) -> bool:
    """Exact bytes, allowing only git core.autocrlf line-ending conversion."""
    lf = data.replace(b"\r\n", b"\n")
    return expected in {
        hashlib.sha256(v).hexdigest() for v in (data, lf, lf.replace(b"\n", b"\r\n"))
    }


def _provenance_for(source_file: str) -> dict:
    prov = SRC / "PROVENANCE.csv"
    with prov.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["stored_filename"] == source_file:
                return row
    raise RuntimeError(f"{source_file} not listed in {prov}")


def _cut(text: str, start: str, end: str | None, after: str | None = None) -> str:
    lines = text.splitlines(keepends=True)
    first = 0
    if after:
        first = next((i for i, l in enumerate(lines) if re.search(after, l)), None)
        if first is None:
            raise RuntimeError(f"'after' anchor not found: {after!r}")
    s = next((i for i in range(first, len(lines)) if re.search(start, lines[i])), None)
    if s is None:
        raise RuntimeError(f"start anchor not found: {start!r}")
    e = len(lines)
    if end:
        e = next((i for i in range(s + 1, len(lines)) if re.search(end, lines[i])), None)
        if e is None:
            raise RuntimeError(f"end anchor not found after start: {end!r}")
    return "".join(lines[s:e]).rstrip() + "\n"


HUPD_SRC = APP_ROOT / "data" / "raw" / "sources" / "hupd_sample_subset"
HUPD_URL = "https://huggingface.co/datasets/HUPD/hupd"
_FIRST_CLAIM_RE = re.compile(r"^\s*1\.\s.*?(?=\s2\.\s|\Z)", re.DOTALL)


def _first_claim(claims: str | None) -> str | None:
    m = _FIRST_CLAIM_RE.match(claims or "")
    return m.group(0).strip() if m else None


def _iso_date(yyyymmdd: str | None) -> str | None:
    v = str(yyyymmdd or "")
    return f"{v[:4]}-{v[4:6]}-{v[6:8]}" if re.fullmatch(r"\d{8}", v) else None


def build_hupd_patents() -> dict:
    """US patent applications (HUPD sample) -> existing patents JSON format.

    Fields are copied, not rewritten: title, abstract, and claim 1 cut from the
    claims text at the start of claim 2. No URL is invented (HUPD provides none).
    """
    src = HUPD_SRC / "hupd_sample_subset.jsonl"
    with (HUPD_SRC / "PROVENANCE.csv").open(encoding="utf-8") as fh:
        prov = next(csv.DictReader(fh))
    src_bytes = src.read_bytes()
    if not _matches_sha256(src_bytes, prov["sha256"]):
        raise RuntimeError(f"{src} does not match its recorded SHA-256")
    records = []
    for line in src_bytes.decode("utf-8").splitlines():
        r = json.loads(line)
        if not (r.get("publication_number") and r.get("title") and r.get("abstract")):
            continue
        records.append({
            "publication_number": r["publication_number"],
            "title": r["title"],
            "abstract": r["abstract"],
            "first_claim": _first_claim(r.get("claims")),
            "url": None,
            "publication_date": _iso_date(r.get("date_published")),
            "jurisdiction": "us",
        })
    doc_id = "hupd_us_herbal_sample"
    doc = OUT / f"{doc_id}.json"
    doc.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    meta = {
        "doc_id": doc_id,
        "title": "US patent applications - HUPD sample, IPC A61K36 (via HF HUPD/hupd)",
        "source_type": "patent",
        "source_url": HUPD_URL,
        "effective_date": None,
        "jurisdiction": "us",
        "legal_scope": "international",
        "section_prefix": None,
        "section_label_prefix": None,
        "is_fixture": False,
    }
    (OUT / f"{doc_id}.meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"[OK] {doc.name}: {len(records)} US patent applications ({doc.stat().st_size:,} bytes)")
    return {
        "doc_id": doc_id,
        "corpus_file": doc.name,
        "scope": f"{len(records)} records; main IPC A61K36; US only (legal_scope=international)",
        "authority_level": "C (research dataset; US applications, not Indian patents)",
        "derived_from": "data/raw/sources/hupd_sample_subset/hupd_sample_subset.jsonl",
        "derived_from_sha256": prov["sha256"],
        "original_source_url": "USPTO (per HUPD)",
        "upstream_dataset": HUPD_URL,
        "upstream_revision": prov["upstream_revision"],
        "built_utc": TODAY,
        "sha256": hashlib.sha256(doc.read_bytes()).hexdigest(),
        "bytes": doc.stat().st_size,
    }


SOURCES_ROOT = APP_ROOT / "data" / "raw" / "sources"

# Glyphs the Indian Kanoon PDF export substitutes for punctuation/symbols, read off
# context: "‡-crystal form" (β), "10 ‹mol/liter" (µ), "211Œ-213Œ" (°), "GleevecŽ" (®).
# "†" is almost always a dash; the one "†crystal (sic ‡-crystal)" (α) stays wrong.
_KANOON_GLYPHS = {
    "□": "“", "‚": "”", "„": "‘", "ƒ": "’", "†": "–", "€": "…", "‡": "β",
    "‹": "µ", "Œ": "°", "Ž": "®", "‰": "•", "Š": "—",
}

PDF_DOCS = [
    {
        "doc_id": "cgpdtm_ayush_guidelines_2025",
        "source_dir": "cgpdtm_ayush_guidelines_2025",
        "source_file": "ayush_examination_guidelines_2025.pdf",
        "title": "Guidelines for Examination of Ayush Related Inventions (CGPDTM, 2025)",
        "source_type": "guideline",
        "mode": "prose",
        "char_fixes": {"\uf0b7": "•", "\xad": ""},
        "scope": "Full document incl. cover pages listing granted Ayush patents",
    },
    {
        "doc_id": "cgpdtm_pharma_guidelines_draft_2026",
        "source_dir": "cgpdtm_pharma_guidelines_draft_2026",
        "source_file": "pharma_examination_guidelines_draft_2026.pdf",
        "title": (
            "DRAFT Guidelines for Examination of Patent Applications in the Field of "
            "Pharmaceuticals (CGPDTM, 2026)"
        ),
        "source_type": "guideline",
        "mode": "prose",
        "layout": True,  # default extraction emits one word per line for this PDF
        "scope": "Full DRAFT document (Hindi cover text is garbled by extraction)",
    },
    {
        "doc_id": "sc_novartis_v_uoi_2013",
        "source_dir": "sc_novartis_v_uoi_2013",
        "source_file": "novartis_v_union_of_india_2013.pdf",
        "title": "Novartis AG v. Union of India & Ors (Supreme Court of India, 1 April 2013)",
        "source_type": "case_law",
        "source_url": "http://indiankanoon.org/doc/165776436/",
        "effective_date": "2013-04-01",
        "mode": "prose",
        "char_fixes": _KANOON_GLYPHS,
        "scope": "Full judgment (Civil Appeal Nos. 2706-2716 of 2013)",
    },
    {
        "doc_id": "api_part1_vol1",
        "source_dir": "ayurvedic_pharmacopoeia_india",
        "source_file": "api_part1_vol1.pdf",
        "title": "The Ayurvedic Pharmacopoeia of India, Part I, Vol. I",
        "source_type": "prior_art",
        "mode": "pharmacopoeia",
        "fonts": "A",
        "scope": "Single-drug monographs; legacy-font diacritics restored to IAST",
    },
    {
        "doc_id": "api_part2_vol2",
        "source_dir": "ayurvedic_pharmacopoeia_india",
        "source_file": "api_part2_vol2.pdf",
        "title": "The Ayurvedic Pharmacopoeia of India, Part II (Formulations), Vol. II",
        "source_type": "prior_art",
        "effective_date": "2009-01-01",
        "mode": "pharmacopoeia",
        "fonts": "AB",
        "scope": "Formulation monographs; diacritics restored; Kruti-Dev Sanskrit verses dropped",
    },
    {
        "doc_id": "afi_part1",
        "source_dir": "ayurvedic_formulary_india",
        "source_file": "afi_part1.pdf",
        "title": "The Ayurvedic Formulary of India, Part I (Second Revised Edition)",
        "source_type": "prior_art",
        "mode": "pharmacopoeia",
        "fonts": "A",
        "scope": "Compound formulations; diacritics restored; Devanagari-font Sanskrit verses dropped",
    },
    {
        "doc_id": "turmeric_patent_review_2021",
        "source_dir": "turmeric_patent_review_2021",
        "source_file": "turmeric_patent_case_review_2021.pdf",
        "title": "A Brief Review on the Turmeric Patent Case (NDC E-BIOS 1:83-88, 2021)",
        "source_type": "comparative_ip",
        "jurisdiction": "us",
        "legal_scope": "international",
        "mode": "prose",
        "scope": "Full article (US turmeric patent revocation; TK documentation)",
    },
    {
        "doc_id": "official_biological_diversity_act_2002",
        "source_dir": "official_biological_diversity_act_2002",
        "source_file": "biological_diversity_act_2002_official.pdf",
        "title": "The Biological Diversity Act, 2002 (Official Gazette)",
        "source_type": "statute",
        "jurisdiction": "india",
        "legal_scope": "domestic",
        "section_label_prefix": "BDA",
        "mode": "prose",
        "scope": "Official gazette version",
    },
    {
        "doc_id": "bda_guidelines_2014",
        "source_dir": "bda_guidelines_2014",
        "source_file": "bda_guidelines_2014.pdf",
        "title": "Guidelines on Access to Biological Resources and Associated Knowledge and Benefits Sharing Regulations, 2014",
        "source_type": "guideline",
        "jurisdiction": "india",
        "legal_scope": "domestic",
        "mode": "prose",
        "scope": "National Biodiversity Authority guidelines",
    },
    {
        "doc_id": "uspto_mpep_2100",
        "source_dir": "uspto_mpep_2100",
        "source_file": "mpep_2100.pdf",
        "title": "MPEP Chapter 2100 Patentability",
        "source_type": "guideline",
        "jurisdiction": "us",
        "legal_scope": "international",
        "mode": "prose",
        "scope": "MPEP Chapter 2100",
    },
]


def _user_provenance(source_dir: str, stored_filename: str) -> dict:
    prov = SOURCES_ROOT / source_dir / "PROVENANCE.csv"
    with prov.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["stored_filename"] == stored_filename:
                return row
    raise RuntimeError(f"{stored_filename} not listed in {prov}; run scripts/import_user_sources.py")


def _verified_source(source_dir: str, stored_filename: str) -> tuple[Path, dict]:
    path = SOURCES_ROOT / source_dir / stored_filename
    prov = _user_provenance(source_dir, stored_filename)
    if not _matches_sha256(path.read_bytes(), prov["sha256"]):
        raise RuntimeError(f"{path} does not match its recorded SHA-256")
    return path, prov


def _write_meta(doc_id: str, **fields) -> None:
    meta = {
        "doc_id": doc_id,
        "title": fields["title"],
        "source_type": fields["source_type"],
        "source_url": fields.get("source_url"),
        "effective_date": fields.get("effective_date"),
        "jurisdiction": fields.get("jurisdiction", "india"),
        "legal_scope": fields.get("legal_scope", "domestic"),
        "section_prefix": fields.get("section_prefix"),
        "section_label_prefix": fields.get("section_label_prefix"),
        "is_fixture": False,
    }
    (OUT / f"{doc_id}.meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8", newline="\n")


def _user_row(doc: Path, doc_id: str, scope: str, source_dir: str, prov: dict) -> dict:
    return {
        "doc_id": doc_id,
        "corpus_file": doc.name,
        "scope": scope,
        "authority_level": prov["authority_level"],
        "derived_from": f"data/raw/sources/{source_dir}/{prov['stored_filename']}",
        "derived_from_sha256": prov["sha256"],
        "original_source_url": prov["original_source_url"],
        "upstream_dataset": prov["source_url"],
        "upstream_revision": prov["upstream_revision"],
        "built_utc": TODAY,
        "sha256": hashlib.sha256(doc.read_bytes()).hexdigest(),
        "bytes": doc.stat().st_size,
    }


def build_pdf_doc(spec: dict) -> dict:
    path, prov = _verified_source(spec["source_dir"], spec["source_file"])
    pages = extract_pages(path, layout=spec.get("layout", False))
    dropped = 0
    if spec["mode"] == "pharmacopoeia":
        page_lines, dropped = clean_pharmacopoeia_pages(pages, spec["fonts"])
        text = pharmacopoeia_text(page_lines)
    else:
        text = reflow_prose(strip_page_furniture(pages))
    for bad, good in spec.get("char_fixes", {}).items():
        text = text.replace(bad, good)
    if not text.strip():
        raise RuntimeError(f"{path.name}: no text extracted")
    doc = OUT / f"{spec['doc_id']}.md"
    doc.write_text(text, encoding="utf-8", newline="\n")
    _write_meta(**spec)
    odd = Counter(ch for ch in text if ord(ch) > 0x7E and not ("\u0100" <= ch <= "\u1eff"))
    extra = f", dropped {dropped} verse lines" if dropped else ""
    print(f"[OK] {doc.name}: {len(pages)} pages -> {len(text):,} chars{extra}; "
          f"top non-IAST chars {odd.most_common(8)}")
    scope = spec["scope"] + (f"; {dropped} undecodable verse lines dropped" if dropped else "")
    return _user_row(doc, spec["doc_id"], scope, spec["source_dir"], prov)


def build_lens_patents() -> dict:
    """Indian patents (Lens.org export) -> patents JSON. Rows without an abstract are
    skipped (the loader requires one); fields are copied, not rewritten."""
    source_dir, stored = "lens_in_patents", "lens_in_patents_export.csv"
    path, prov = _verified_source(source_dir, stored)
    records, skipped = [], 0
    with path.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            abstract = (r.get("Abstract") or "").strip()
            title = (r.get("Title") or "").strip().strip('"').strip()
            if not abstract or not title:
                skipped += 1
                continue
            records.append({
                "publication_number": r["Display Key"].strip(),
                "title": title,
                "abstract": abstract,
                "first_claim": None,
                "url": (r.get("URL") or "").strip() or None,
                "publication_date": (r.get("Publication Date") or "").strip() or None,
                "jurisdiction": "india",
            })
    doc_id = "lens_in_patents"
    doc = OUT / f"{doc_id}.json"
    doc.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    _write_meta(
        doc_id,
        title="Indian patent documents - Lens.org export",
        source_type="patent",
        source_url="https://lens.org",
    )
    print(f"[OK] {doc.name}: {len(records)} IN patent records ({skipped} skipped: no abstract/title)")
    scope = (f"{len(records)} IN records with abstracts ({skipped} of {len(records) + skipped} "
             "skipped: no abstract); broad export incl. non-herbal subject matter")
    return _user_row(doc, doc_id, scope, source_dir, prov)


def build_bhaishajya_kalpana_kosha() -> dict:
    source_dir, stored = "bhaishajya_kalpana_kosha", "bhaishajya_kalpana_kosha.json"
    path, prov = _verified_source(source_dir, stored)
    
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    doc_id = "bhaishajya_kalpana_kosha"
    doc = OUT / f"{doc_id}.md"
    
    md_lines = []
    for d in data:
        name = d.get("name", "")
        type_ = d.get("type", "")
        md_lines.append(f"{name} ({type_})")
        md_lines.append("")
        
        para = []
        if d.get("category"):
            para.append(f"Category: {d.get('category')}")
        if d.get("main_ingredients"):
            para.append(f"Main ingredients: {', '.join(d.get('main_ingredients'))}")
        if d.get("ingredients"):
            para.append(f"Ingredients: {d.get('ingredients')}")
        if d.get("reference"):
            para.append(f"Reference: {d.get('reference')}")
        if d.get("indications"):
            para.append(f"Indications: {d.get('indications')}")
        if d.get("dosage"):
            para.append(f"Dosage: {d.get('dosage')}")
        if d.get("anupana"):
            para.append(f"Anupana: {d.get('anupana')}")
            
        md_lines.append("\n".join(para))
        md_lines.append("")
    
    text = "\n".join(md_lines).strip() + "\n"
    doc.write_text(text, encoding="utf-8", newline="\n")
    
    _write_meta(
        doc_id,
        title="Bhaishajya Kalpana Kosha - classical Ayurvedic formulations (user-supplied dataset)",
        source_type="prior_art",
        source_url=None,
    )
    
    print(f"[OK] {doc.name}: {len(data)} formulations")
    scope = f"{len(data)} formulations rendered from JSON to Markdown; fields copied verbatim; duplicate records kept."
    return _user_row(doc, doc_id, scope, source_dir, prov)


def build_us_turmeric_patent() -> dict:
    source_dir, stored = "us_turmeric_patent", "us5401504.pdf"
    path, prov = _verified_source(source_dir, stored)

    doc_id = "us_turmeric_patent_us5401504"
    doc = OUT / f"{doc_id}.json"

    abstract = "Method of promoting healing of a wound by administering turmeric to a patient afflicted with the wound."
    first_claim = "1. A method of promoting healing of a wound in a patient, which consists essentially of administering a wound-healing agent consisting of an effective amount of turmeric powder to said patient."

    records = [{
        "publication_number": "US5401504A",
        "title": "USE OF TURMERIC IN WOUND HEALING",
        "abstract": abstract,
        "first_claim": first_claim,
        "url": None,
        "publication_date": "1995-03-28",
        "jurisdiction": "us"
    }]
    
    doc.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    _write_meta(
        doc_id,
        title="US Patent 5401504A - USE OF TURMERIC IN WOUND HEALING",
        source_type="patent",
        source_url=None,
        jurisdiction="us",
        legal_scope="international"
    )
    
    print(f"[OK] {doc.name}: 1 US patent record")
    scope = "Extracted US Patent 5401504A (Abstract and Claim 1 hardcoded from PDF text)"
    return _user_row(doc, doc_id, scope, source_dir, prov)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for spec in EXTRACTS:
        src_path = SRC / spec["source_file"]
        prov = _provenance_for(spec["source_file"])
        src_bytes = src_path.read_bytes()
        if not _matches_sha256(src_bytes, prov["sha256"]):
            raise RuntimeError(f"{src_path} does not match its recorded SHA-256")
        text = src_bytes.decode("utf-8").replace("\r\n", "\n")
        excerpt = _cut(text, spec["start"], spec["end"], spec.get("after"))
        doc = OUT / f"{spec['doc_id']}.md"
        doc.write_text(excerpt, encoding="utf-8", newline="\n")
        meta = {
            "doc_id": spec["doc_id"],
            "title": spec["title"],
            "source_type": "statute",
            "source_url": HF_URL,
            "effective_date": None,  # not stated in the source text; see CORPUS_PROVENANCE.csv
            "jurisdiction": "india",
            "legal_scope": "domestic",
            "section_prefix": None,
            "section_label_prefix": spec.get("section_label_prefix"),
            "is_fixture": False,
        }
        (OUT / f"{spec['doc_id']}.meta.json").write_text(
            json.dumps(meta, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        rows.append({
            "doc_id": spec["doc_id"],
            "corpus_file": doc.name,
            "scope": spec["scope"],
            "authority_level": "C (secondary dataset; not authoritative law)",
            "derived_from": f"data/raw/sources/hf_indian_legal_acts/{spec['source_file']}",
            "derived_from_sha256": prov["sha256"],
            "original_source_url": prov["original_source_url"],
            "upstream_dataset": HF_URL,
            "upstream_revision": prov["upstream_revision"],
            "built_utc": TODAY,
            "sha256": hashlib.sha256(doc.read_bytes()).hexdigest(),
            "bytes": doc.stat().st_size,
        })
        print(f"[OK] {doc.name}: {spec['scope']} ({doc.stat().st_size:,} bytes)")
    rows.append(build_hupd_patents())
    rows.append(build_lens_patents())
    rows.append(build_bhaishajya_kalpana_kosha())
    rows.append(build_us_turmeric_patent())
    rows.extend(build_pdf_doc(spec) for spec in PDF_DOCS)
    with (OUT / "CORPUS_PROVENANCE.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
