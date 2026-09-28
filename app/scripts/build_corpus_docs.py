"""Build ingestible corpus documents (layer B) from fetched source files (layer A).

Run from app/ after scripts/fetch_sources.py:

    uv run python scripts/build_corpus_docs.py

Reads   data/raw/sources/hf_indian_legal_acts/*.md          (verbatim Act text)
        data/raw/sources/hupd_sample_subset/*.jsonl        (US patent applications)
Writes  data/raw/corpus/<doc_id>.(md|json) + <doc_id>.meta.json + CORPUS_PROVENANCE.csv

Each corpus document is a VERBATIM excerpt of the source text, cut at fixed
anchors (no rewording). Layout artifacts (Markdown, page footnotes, page breaks)
are handled later by the statute chunker, not here. Fails loudly if an anchor
is missing rather than guessing. Does not index anything.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

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
    if hashlib.sha256(src_bytes).hexdigest() != prov["sha256"]:
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


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for spec in EXTRACTS:
        src_path = SRC / spec["source_file"]
        prov = _provenance_for(spec["source_file"])
        src_bytes = src_path.read_bytes()
        if hashlib.sha256(src_bytes).hexdigest() != prov["sha256"]:
            raise RuntimeError(f"{src_path} does not match its recorded SHA-256")
        excerpt = _cut(src_bytes.decode("utf-8"), spec["start"], spec["end"], spec.get("after"))
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
    with (OUT / "CORPUS_PROVENANCE.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
