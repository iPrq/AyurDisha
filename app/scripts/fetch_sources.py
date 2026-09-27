"""Fetch the approved AyurDisha MVP source files into data/raw/sources/.

Run from app/:

    uv pip install huggingface_hub pyarrow
    uv run python scripts/fetch_sources.py

What it does (and does NOT do):
- Downloads ONLY the approved subsets; originals are stored byte-for-byte where kept.
- Writes a PROVENANCE.csv per source folder.
- Never writes *.meta.json sidecars, so nothing here is picked up by ingestion.
- Never touches data/processed/, Qdrant, embeddings or BM25.

Sources (see docs discussion 2026-09-27):
  hf_indian_legal_acts   HF geekyrakshit/indian-legal-acts   (Level C, secondary)
  hupd_sample_subset     HF HUPD/hupd sample, ~30 records    (Level C, US only)
  amidha_herb_db_v2      GitHub herb-database                (Level C, CC-BY-4.0)
  indiaspend_patents_2015 GitHub patents_2015, filtered      (Level C, Unlicense)
  tv_ca_india_inventory  GitHub tv-ca-india, relevant rows   (Level B catalogue, MIT)
  kaggle_laws_acts       optional (--kaggle), listed only unless small
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = APP_ROOT / "data" / "raw" / "sources"
TODAY = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

PROVENANCE_FIELDS = [
    "source_id", "source_name", "source_url", "source_type", "authority_level",
    "jurisdiction", "retrieval_date_utc", "original_filename", "stored_filename",
    "document_title", "original_source_url", "upstream_revision", "license",
    "sha256", "bytes", "notes",
]

# Acts to extract from the HF dataset (matched on normalized short title).
TARGET_ACTS = {
    "patents act 1970": "patents_act_1970",
    "biological diversity act 2002": "biological_diversity_act_2002",
    "drugs and cosmetics act 1940": "drugs_and_cosmetics_act_1940",
}

# GitHub sources pinned to the exact commits inspected on 2026-09-27.
GH_HERB = {
    "repo": "sciencewithsaucee-sudo/herb-database",
    "commit": "9793cd44a6bb9fcebf11e4fea2f646030cf98366",
    "path": "herb.json",
    "sha256": "93a7dd1f244b931e5dcf82a9fe37112d549370c05b6c0eefb2b1cd81ae8a4140",
}
GH_PATENTS = {
    "repo": "shijithpk/patents_2015",
    "commit": "10915fcf52d6c645d1fad562b0af89acdf8cd064",
    "path": "complete_data_set.csv",
    "sha256": "6b86f51adfa3ecb8bf7200796952352d130c5e3e6d1b6d73132c6a5a3be7f4e9",
}
GH_INVENTORY = {
    "repo": "NoelShallum/tv-ca-india",
    "commit": "961f10347a934ff0ae805edfc332c3506fac5cb7",
    "path": "data/central_acts_inventory.csv",
    "sha256": "5aa2c4712b7cf14d37557998016d8dc6ebd82f41be529055cf53188543ba5d7e",
}
INVENTORY_TITLES = {
    "The Patents Act, 1970",
    "The Biological Diversity Act, 2002",
    "The Drugs and Cosmetics Act, 1940",
    "The Trade Marks Act, 1999",
    "The Designs Act, 2000",
    "The Geographical Indications of Goods (Registration and Protection) Act, 1999",
}

HERBAL_TITLE_RE = re.compile(
    r"ayurved|curcum|turmeric|withania|ashwagandh|polyherbal|herbal", re.IGNORECASE
)
# Columns in the IndiaSpend CSV that contain personal addresses — dropped.
PII_COLUMNS = {
    "inventor.unparsed", "applicant.unparsed",
    "inventor.address.ACTUAL", "inventor.address.1st",
}

HUPD_MAX_BYTES = 1_000_000_000  # refuse to download a "sample" larger than ~1 GB
HUPD_CAP = 30


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_provenance(folder: Path, rows: list[dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "PROVENANCE.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=PROVENANCE_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in PROVENANCE_FIELDS})


def github_raw(src: dict) -> tuple[bytes, str]:
    url = f"https://raw.githubusercontent.com/{src['repo']}/{src['commit']}/{src['path']}"
    with urllib.request.urlopen(url, timeout=120) as resp:  # noqa: S310 - fixed https URL
        data = resp.read()
    got = sha256_bytes(data)
    if got != src["sha256"]:
        raise RuntimeError(
            f"SHA-256 mismatch for {url}: expected {src['sha256']}, got {got}"
        )
    return data, url


def norm_title(title: str) -> str:
    t = re.sub(r"[^a-z0-9 ]+", " ", (title or "").lower())
    t = re.sub(r"^\s*the\s+", "", t)
    return " ".join(t.split())


def pick_column(columns: list[str], candidates: list[str]) -> str | None:
    lower = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    return None


# ---------------------------------------------------------------------------
# GitHub sources
# ---------------------------------------------------------------------------


def fetch_herb_db(out: Path) -> str:
    folder = out / "amidha_herb_db_v2"
    data, url = github_raw(GH_HERB)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "herb.json").write_bytes(data)
    write_provenance(folder, [{
        "source_id": "amidha_herb_db_v2",
        "source_name": "Amidha Ayurveda Herb Database v2.0",
        "source_url": f"https://github.com/{GH_HERB['repo']}",
        "source_type": "botanical_reference",
        "authority_level": "C",
        "jurisdiction": "",
        "retrieval_date_utc": TODAY,
        "original_filename": "herb.json",
        "stored_filename": "herb.json",
        "document_title": "Amidha Ayurveda Herb Database v2.0 (360 herbs)",
        "original_source_url": "https://www.amidhaayurveda.com/p/herb-database.html",
        "upstream_revision": GH_HERB["commit"],
        "license": "CC-BY-4.0",
        "sha256": GH_HERB["sha256"],
        "bytes": len(data),
        "notes": (
            "Curated by an individual publisher; no per-record primary citations. "
            "Botanical/terminology metadata only - not legal evidence. MVP uses "
            "Ashwagandha (Withania somnifera) and Haridra (Curcuma longa). Repo "
            "cites two different DOIs (10.5281/zenodo.20581467 and 17475351)."
        ),
    }])
    return f"herb.json ({len(data):,} bytes, sha256 verified)"


def fetch_indiaspend_subset(out: Path) -> str:
    folder = out / "indiaspend_patents_2015"
    data, url = github_raw(GH_PATENTS)
    csv.field_size_limit(2**31 - 1)  # fits a C long on Windows too
    reader = csv.DictReader(io.StringIO(data.decode("utf-8", errors="replace")))
    keep_cols = [c for c in (reader.fieldnames or []) if c not in PII_COLUMNS]
    subset = [
        {c: row[c] for c in keep_cols}
        for row in reader
        if HERBAL_TITLE_RE.search(row.get("record_title", ""))
        and (
            row.get("classification_ipcr", "").startswith("A61K")
            or "PHARMA" in row.get("field_of_invention", "").upper()
        )
    ]
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / "subset_ayurveda_herbal.csv"
    with stored.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keep_cols)
        w.writeheader()
        w.writerows(subset)
    write_provenance(folder, [{
        "source_id": "indiaspend_patents_2015",
        "source_name": "IndiaSpend patents dataset (patents granted in India 2005-2015)",
        "source_url": f"https://github.com/{GH_PATENTS['repo']}",
        "source_type": "patent_metadata",
        "authority_level": "C",
        "jurisdiction": "india",
        "retrieval_date_utc": TODAY,
        "original_filename": "complete_data_set.csv",
        "stored_filename": stored.name,
        "document_title": "Indian granted patents 2005-2015 - Ayurveda/herbal pharma subset",
        "original_source_url": "not stated by upstream (likely Indian Patent Office; UNVERIFIED)",
        "upstream_revision": GH_PATENTS["commit"],
        "license": "Unlicense (public domain dedication)",
        "sha256": sha256_file(stored),
        "bytes": stored.stat().st_size,
        "notes": (
            f"Derived subset: {len(subset)} rows where title matches "
            f"'{HERBAL_TITLE_RE.pattern}' AND (IPC starts A61K OR field is pharmaceuticals). "
            f"Columns removed for privacy: {sorted(PII_COLUMNS)}. Upstream full-file "
            f"sha256={GH_PATENTS['sha256']} (not stored: contains personal addresses). "
            "No abstracts or claims in upstream data."
        ),
    }])
    return f"{stored.name} ({len(subset)} rows, address columns removed)"


def fetch_inventory_rows(out: Path) -> str:
    folder = out / "tv_ca_india_inventory"
    data, url = github_raw(GH_INVENTORY)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "central_acts_inventory.csv").write_bytes(data)
    reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
    rows = [r for r in reader if r.get("title") in INVENTORY_TITLES]
    stored = folder / "relevant_acts.csv"
    with stored.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=reader.fieldnames or [])
        w.writeheader()
        w.writerows(rows)
    base = {
        "source_name": "Time-Versioned Central Acts of India - India Code inventory",
        "source_url": f"https://github.com/{GH_INVENTORY['repo']}",
        "source_type": "legal_catalogue",
        "authority_level": "B",
        "jurisdiction": "india",
        "retrieval_date_utc": TODAY,
        "original_filename": "central_acts_inventory.csv",
        "original_source_url": "https://indiacode.gov.in (per-row api_url/public_url)",
        "upstream_revision": GH_INVENTORY["commit"],
        "license": "MIT",
    }
    write_provenance(folder, [
        {**base, "source_id": "tv_ca_india_inventory",
         "stored_filename": "central_acts_inventory.csv",
         "document_title": "India Code central-acts inventory snapshot (2026-09-10)",
         "sha256": GH_INVENTORY["sha256"], "bytes": len(data),
         "notes": "Catalogue only - no Act text. Upstream README states a different "
                  "SHA-256 (4527A35E...); file likely changed after README."},
        {**base, "source_id": "tv_ca_india_inventory_relevant",
         "stored_filename": stored.name,
         "document_title": "Inventory rows for AyurDisha-relevant Acts",
         "sha256": sha256_file(stored), "bytes": stored.stat().st_size,
         "notes": f"Derived: {len(rows)} rows for {sorted(INVENTORY_TITLES)}"},
    ])
    return f"central_acts_inventory.csv + {stored.name} ({len(rows)} rows)"


# ---------------------------------------------------------------------------
# Hugging Face sources
# ---------------------------------------------------------------------------


def fetch_hf_legal_acts(out: Path) -> str:
    from huggingface_hub import HfApi, hf_hub_download
    import pyarrow.parquet as pq

    repo = "geekyrakshit/indian-legal-acts"
    api = HfApi()
    info = api.dataset_info(repo, files_metadata=True)
    revision = info.sha
    parquet = [s for s in info.siblings if s.rfilename.endswith(".parquet")]
    central = [s for s in parquet if "central" in s.rfilename.lower()]
    chosen = central or parquet
    if not chosen:
        raise RuntimeError(f"No parquet files found in {repo}; files: {[s.rfilename for s in info.siblings]}")

    folder = out / "hf_indian_legal_acts"
    orig_dir = folder / "original"
    orig_dir.mkdir(parents=True, exist_ok=True)
    prov: list[dict] = []
    found: dict[str, dict] = {}
    columns_seen: list[str] = []

    for sib in chosen:
        cached = hf_hub_download(repo, sib.rfilename, repo_type="dataset", revision=revision)
        stored = orig_dir / Path(sib.rfilename).name
        shutil.copyfile(cached, stored)
        prov.append({
            "source_id": "hf_indian_legal_acts",
            "source_name": "Indian Legal Acts (Hugging Face)",
            "source_url": f"https://huggingface.co/datasets/{repo}",
            "source_type": "legal_text_dataset",
            "authority_level": "C",
            "jurisdiction": "india",
            "retrieval_date_utc": TODAY,
            "original_filename": sib.rfilename,
            "stored_filename": f"original/{stored.name}",
            "document_title": "Indian legal acts (parquet split, verbatim copy)",
            "original_source_url": "https://www.indiacode.nic.in (per-row PDF link column)",
            "upstream_revision": revision,
            "license": "not stated on dataset card",
            "sha256": sha256_file(stored),
            "bytes": stored.stat().st_size,
            "notes": "Secondary dataset; Markdown converted from PDFs by the dataset author. Not authoritative law.",
        })
        table = pq.read_table(stored)
        columns_seen = table.column_names
        title_col = pick_column(columns_seen, ["Short Title", "short_title", "title"])
        if not title_col:
            raise RuntimeError(f"No title column in {sib.rfilename}: {columns_seen}")
        for row in table.to_pylist():
            key = norm_title(row.get(title_col, ""))
            if key in TARGET_ACTS:
                found.setdefault(key, {"row": row, "file": sib.rfilename})

    text_col = pick_column(columns_seen, ["Markdown", "markdown", "text", "content"])
    url_col = pick_column(columns_seen, ["View", "view", "pdf", "url", "link"])
    with (folder / "selected_acts.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for key, hit in found.items():
            fh.write(json.dumps({"target": TARGET_ACTS[key], "from_file": hit["file"], **hit["row"]},
                                ensure_ascii=False, default=str) + "\n")
    for key, hit in found.items():
        slug = TARGET_ACTS[key]
        if text_col and hit["row"].get(text_col):
            md = folder / f"{slug}.md"
            md.write_text(str(hit["row"][text_col]), encoding="utf-8", newline="\n")
            prov.append({
                "source_id": f"hf_indian_legal_acts:{slug}",
                "source_name": "Indian Legal Acts (Hugging Face)",
                "source_url": f"https://huggingface.co/datasets/{repo}",
                "source_type": "legal_text_dataset",
                "authority_level": "C",
                "jurisdiction": "india",
                "retrieval_date_utc": TODAY,
                "original_filename": hit["file"],
                "stored_filename": md.name,
                "document_title": str(hit["row"].get(title_col, "")),
                "original_source_url": str(hit["row"].get(url_col, "")) if url_col else "",
                "upstream_revision": revision,
                "license": "not stated on dataset card",
                "sha256": sha256_file(md),
                "bytes": md.stat().st_size,
                "notes": f"'{text_col}' field of the row, written verbatim. Version/'as on' date must be checked in the text.",
            })
    write_provenance(folder, prov)
    missing = [TARGET_ACTS[k] for k in TARGET_ACTS if k not in found]
    msg = f"{len(found)}/{len(TARGET_ACTS)} Acts found; columns={columns_seen}"
    if missing:
        msg += f"; NOT FOUND (not guessed): {missing}"
    return msg


def fetch_hupd_subset(out: Path) -> str:
    from huggingface_hub import HfApi, hf_hub_download

    repo = "HUPD/hupd"
    api = HfApi()
    info = api.dataset_info(repo, files_metadata=True)
    samples = [
        s for s in info.siblings
        if "sample" in s.rfilename.lower() and s.rfilename.endswith((".tar.gz", ".tgz", ".tar"))
    ]
    if not samples:
        return ("SKIPPED: no sample archive found. Files: "
                + ", ".join(s.rfilename for s in info.siblings[:30]))
    sample = min(samples, key=lambda s: s.size or 0)
    if (sample.size or 0) > HUPD_MAX_BYTES:
        return f"SKIPPED: {sample.rfilename} is {sample.size:,} bytes (> {HUPD_MAX_BYTES:,} limit)"

    cached = Path(hf_hub_download(repo, sample.rfilename, repo_type="dataset", revision=info.sha))
    archive_sha = sha256_file(cached)
    picked: list[dict] = []
    with tarfile.open(cached, "r:*") as tar:
        for member in tar:
            if len(picked) >= HUPD_CAP:
                break
            if not member.isfile() or not member.name.endswith(".json"):
                continue
            fh = tar.extractfile(member)
            if fh is None:
                continue
            try:
                rec = json.load(fh)
            except ValueError:
                continue
            main = str(rec.get("main_ipcr_label", "")).replace(" ", "").replace("/", "").upper()
            # MAIN IPC label A61K 36 = medicinal preparations containing plant/fungal/algal
            # material. Keywords and secondary labels were dropped: they admitted e.g.
            # herbal grinders and sonic devices.
            if main.startswith("A61K36"):
                picked.append({"_archive_member": member.name, **rec})

    folder = out / "hupd_sample_subset"
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / "hupd_sample_subset.jsonl"
    with stored.open("w", encoding="utf-8", newline="\n") as fh:
        for rec in picked:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    write_provenance(folder, [{
        "source_id": "hupd_sample_subset",
        "source_name": "Harvard USPTO Patent Dataset (HUPD) - sample subset",
        "source_url": f"https://huggingface.co/datasets/{repo}",
        "source_type": "patent_records",
        "authority_level": "C",
        "jurisdiction": "us",
        "retrieval_date_utc": TODAY,
        "original_filename": sample.rfilename,
        "stored_filename": stored.name,
        "document_title": f"HUPD sample - first {len(picked)} records whose main IPC label is A61K36",
        "original_source_url": "USPTO (per HUPD)",
        "upstream_revision": info.sha,
        "license": "CC-BY-SA-4.0 (per dataset card; card also mentions NonCommercial - check)",
        "sha256": sha256_file(stored),
        "bytes": stored.stat().st_size,
        "notes": (f"US applications only - NOT Indian patents; tag legal_scope=international. "
                  f"Archive sha256={archive_sha} ({sample.size:,} bytes) kept in HF cache, not in raw/."),
    }])
    return f"{stored.name} ({len(picked)} records from {sample.rfilename})"


# ---------------------------------------------------------------------------
# Kaggle (optional)
# ---------------------------------------------------------------------------


def fetch_kaggle(out: Path) -> str:
    slug = "kausthubkannan/laws-and-acts-of-india"
    if shutil.which("kaggle") is None:
        return "SKIPPED: kaggle CLI not installed (uv pip install kaggle) or no token"
    listing = subprocess.run(
        ["kaggle", "datasets", "files", slug, "--csv"],
        capture_output=True, text=True, timeout=120,
    )
    folder = out / "kaggle_laws_acts"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "FILE_LISTING.csv").write_text(listing.stdout or listing.stderr, encoding="utf-8")
    return ("Listed files only -> kaggle_laws_acts/FILE_LISTING.csv. Review before downloading "
            "(contents were unverified).")


# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--skip-github", action="store_true")
    p.add_argument("--skip-hf", action="store_true", help="skip HF indian-legal-acts")
    p.add_argument("--skip-hupd", action="store_true")
    p.add_argument("--kaggle", action="store_true", help="list Kaggle dataset files (optional)")
    args = p.parse_args(argv)

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    steps = []
    if not args.skip_github:
        steps += [("amidha_herb_db_v2", fetch_herb_db),
                  ("indiaspend_patents_2015", fetch_indiaspend_subset),
                  ("tv_ca_india_inventory", fetch_inventory_rows)]
    if not args.skip_hf:
        steps.append(("hf_indian_legal_acts", fetch_hf_legal_acts))
    if not args.skip_hupd:
        steps.append(("hupd_sample_subset", fetch_hupd_subset))
    if args.kaggle:
        steps.append(("kaggle_laws_acts", fetch_kaggle))

    report = [f"# Fetch report {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}"]
    failures = 0
    for name, fn in steps:
        try:
            msg = fn(out)
            status = "SKIPPED" if msg.startswith("SKIPPED") else "OK"
        except Exception as exc:  # noqa: BLE001 - report and continue with other sources
            failures += 1
            status, msg = "FAILED", f"{type(exc).__name__}: {exc}"
        line = f"[{status}] {name}: {msg}"
        print(line)
        report.append(line)
    (out / "FETCH_REPORT.log").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"\nReport written to {out / 'FETCH_REPORT.log'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
