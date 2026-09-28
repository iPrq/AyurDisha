"""PDF -> corpus text for user-supplied guideline / case-law / pharmacopoeia sources.

Formatting-only cleanup; wording is never rewritten:
- repeated page headers/footers and bare page numbers are removed;
- prose is reflowed into paragraphs so the guideline chunker sees real boundaries;
- legacy transliteration-font glyphs are mapped back to IAST
  (e.g. "A¿vagandh¡" -> "Aśvagandhā");
- Sanskrit verses encoded in legacy Devanagari fonts (unreadable after extraction)
  are dropped, and the dropped line count is reported.
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from collections import Counter
from pathlib import Path

# --- Legacy transliteration fonts -----------------------------------------------
# Font A: Ayurvedic Pharmacopoeia Part I Vol I, Ayurvedic Formulary Part I, and most
# of API Part II Vol II. Mapping derived from recurring words in those books
# (Kv¡tha = Kvātha, P¤¿nipar¸¢ = Pṛśniparṇī, Gu·£c¢ = Guḍūcī, AáVAGANDHË = AŚVAGANDHĀ).
_FONT_A = {
    "¡": "ā", "¢": "ī", "£": "ū", "¤": "ṛ", "¸": "ṇ", "¶": "ṭ", "·": "ḍ",
    "À": "ṣ", "¿": "ś", "´": "ṅ", "Æ": "ṃ", "®": "e", "Å": "ḥ",
    "á": "Ś", "Ë": "Ā", "Ì": "Ī", "Í": "Ū", "Î": "Ṛ", "Ù": "Ṭ", "Û": "Ṇ",
    "Ú": "Ḍ", "â": "Ṣ", "Ø": "Ñ", "×": "Ṅ", "ê": "Ṃ",
}
# Font B: second font in API Part II Vol II; conflicts with font A on several glyphs
# (Bhai¾ajyaratn¢val¤ = Bhaiṣajyaratnāvalī, Rasatara¬gi´ī = Rasataraṅgiṇī,
# ABHAY¡RI½¯A = ABHAYĀRIṢṬA), so it is applied per word, only where detected.
_FONT_B = {
    "¢": "ā", "¤": "ī", "¦": "ū", "º": "ś", "¾": "ṣ", "°": "ṭ", "¬": "ṅ",
    "´": "ṇ", "¼": "ṃ", "²": "ḍ", "¨": "ṛ", "®": "ñ", "ª": "ḥ",
    "¡": "Ā", "¥": "Ū", "³": "Ṇ", "½": "Ṣ", "¯": "Ṭ", "§": "Ṛ",
}
_FONT_B_ONLY = set("¾¬¼²¨º¦¥³½¯§ª")
_WORD_RE = re.compile(r"\S+")


def _is_font_b_word(word: str) -> bool:
    return any(ch in _FONT_B_ONLY or "\u0100" <= ch <= "\u024f" or "\u1e00" <= ch <= "\u1eff"
               for ch in word)


def _map_word(word: str, fonts: str) -> str:
    use_b = "B" in fonts and _is_font_b_word(word)
    table = _FONT_B if use_b else _FONT_A
    out: list[str] = []
    for i, ch in enumerate(word):
        prev = word[i - 1] if i else ""
        nxt = word[i + 1] if i + 1 < len(word) else ""
        if ch == "µ":
            out.append("ñ" if prev.isalpha() else ch)  # "Paµcasak¡ra" vs "µg"
        elif ch == "°":
            if use_b:
                out.append("ṭ")
            else:
                out.append("o" if prev.isalpha() else ch)  # "á°dhana" vs "40°"
        elif ch == "±":
            out.append("Ḍ" if use_b and nxt.isalpha() else ch)  # "±amarū" vs "7.0±0.2"
        elif ch in table:
            out.append(table[ch])
        elif use_b and ch in _FONT_A:
            out.append(_FONT_A[ch])
        else:
            out.append(ch)
    mapped = "".join(out)
    letters = [c for c in word if c.isascii() and c.isalpha()]
    if len(letters) >= 2 and all(c.isupper() for c in letters):
        mapped = mapped.upper()
    return unicodedata.normalize("NFC", mapped)


def fix_legacy_iast(line: str, fonts: str = "A") -> str:
    return _WORD_RE.sub(lambda m: _map_word(m.group(0), fonts), line)


# --- Legacy Devanagari (unreadable after extraction) ------------------------------
# DV-style font (Ayurvedic Formulary): always contains É/Ê, never used by font A.
_DV_MARKERS = set("ÉÊ")
# Kruti-Dev-style font (API Part II): ASCII soup such as "e`fÙkdkifjfu£ers",
# verse lines end with "A" or "AA 105 AA"; source refs wrapped in ¼...½.
_KRUTI_MARKERS = (
    r"[;'\"~`\]}{/\\=Ò](?=\w)",  # "'kk", "/kkrd", "Ò;"
    r"\w[;\"`~\]]",              # "ò;", "e`f", "yh]"
    r"\w~$",
    r"\.k",                      # ".k" = ण
    r"[a-z][A-Z][a-z]",          # "fuEcke", "jRuk"
)
_KRUTI_MARKER_RES = [re.compile(p) for p in _KRUTI_MARKERS]
_KRUTI_STRONG_RE = re.compile(r"[`~]|\w\"\w|\.k|[a-z][A-Z][a-z]")
_UNIT_TOKEN_RE = re.compile(r"^\(?[\d.,]*[µμ]?[a-z]{1,3}/[a-z]{1,3}\)?[,.;:)]*$", re.IGNORECASE)
_KRUTI_VERSE_NO_RE = re.compile(r"AA\s*\d+\s*AA?\*?\s*$")
_KRUTI_HALF_VERSE_RE = re.compile(r"\sAA?\*?\s*$")
_KRUTI_SPAN_RE = re.compile(r"¼[^½\s]{2,30}½|¼[^½\s][^½]*?[;\"'`~\]/][^½]*?½")


def _kruti_markers(token: str) -> int:
    if _UNIT_TOKEN_RE.match(token):
        return 0
    return sum(1 for r in _KRUTI_MARKER_RES if r.search(token))


def is_devanagari_verse(line: str, fonts: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if any(ch in _DV_MARKERS for ch in s):
        return True
    if "B" not in fonts:
        return False
    if _KRUTI_VERSE_NO_RE.search(s):
        return True
    tokens = s.split()
    markers = [_kruti_markers(t) for t in tokens]
    hits = sum(1 for m in markers if m)
    if hits and _KRUTI_HALF_VERSE_RE.search(s):
        return True
    if len(tokens) == 1:
        return len(s) >= 8 and markers[0] >= 2 and bool(_KRUTI_STRONG_RE.search(s))
    return hits / len(tokens) >= 0.4


# --- Extraction + page cleanup ---------------------------------------------------
_PAGE_NUM_RE = re.compile(r"^\s*(?:page\s+)?\d{1,4}(?:\s+of\s+\d{1,4})?\s*$", re.IGNORECASE)
_RULE_RE = re.compile(r"^\s*[-_=]{5,}\s*$")


def extract_pages(path: Path, *, layout: bool = False) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    mode = {"extraction_mode": "layout"} if layout else {}
    return [(page.extract_text(**mode) or "") for page in reader.pages]


def _norm_repeat_key(line: str) -> str:
    return re.sub(r"\d+", "#", " ".join(line.split())).lower()


_EDGE_LINES = 3


def _edges(lines: list[str]) -> set[int]:
    n = len(lines)
    return set(range(min(_EDGE_LINES, n))) | set(range(max(0, n - _EDGE_LINES), n))


def strip_page_furniture(pages: list[str], min_fraction: float = 0.3) -> list[list[str]]:
    """Split pages into lines; drop page numbers and headers/footers, i.e. lines at the
    top/bottom of a page that repeat there on many pages. Repeated section labels in the
    page body (SYNONYMS, Dose, ...) are kept."""
    page_lines = [[ln.rstrip() for ln in p.splitlines() if ln.strip()] for p in pages]
    counts: Counter[str] = Counter()
    for lines in page_lines:
        counts.update({_norm_repeat_key(lines[i]) for i in _edges(lines)})
    threshold = max(3, int(len(pages) * min_fraction))
    repeated = {k for k, v in counts.items() if v >= threshold}
    out: list[list[str]] = []
    for lines in page_lines:
        edges = _edges(lines)
        out.append([
            " ".join(ln.split()) for i, ln in enumerate(lines)
            if not (i in edges and _norm_repeat_key(ln) in repeated)
            and not _PAGE_NUM_RE.match(ln)
            and not _RULE_RE.match(ln)
        ])
    return out


# --- Prose reflow ----------------------------------------------------------------
_BLOCK_START_RE = re.compile(
    r"^(?:\d{1,2}(?:\.\d{1,2})*\.?\s|\(?[a-z]\)\s|\(?[ivxl]{1,5}\)\s|[●•▪◦–-]\s"
    r"|Section\s+\d|Explanation\b|Illustration\b|Example\b)"
)
_TERMINAL = (".", ":", "?", "!", ".\"", ".”", ".’", ";")
PROSE_MAX_CHARS = 1500
_SENTENCE_END_RE = re.compile(r"(?<=[.;?!”\"])\s+(?=[\"“(A-Z0-9])")


def _split_long(paragraph: str, max_chars: int = PROSE_MAX_CHARS) -> list[str]:
    """Split an oversized paragraph at sentence ends (whole sentences, never mid-word)."""
    if len(paragraph) <= max_chars:
        return [paragraph]
    parts: list[str] = []
    cur = ""
    for sentence in _SENTENCE_END_RE.split(paragraph):
        if cur and len(cur) + len(sentence) + 1 > max_chars:
            parts.append(cur)
            cur = sentence
        else:
            cur = f"{cur} {sentence}" if cur else sentence
    if cur:
        parts.append(cur)
    return parts


def reflow_prose(pages: list[list[str]]) -> str:
    lines = [ln for page in pages for ln in page]
    if not lines:
        return ""
    median = statistics.median(len(ln) for ln in lines)
    paras: list[list[str]] = []
    for ln in lines:
        if not paras:
            paras.append([ln])
            continue
        cur = paras[-1]
        prev = cur[-1]
        prev_is_heading = len(cur) == 1 and len(prev) < 0.6 * median and not prev.endswith(_TERMINAL)
        prev_ends_para = prev.endswith(_TERMINAL) and len(prev) < 0.85 * median
        if _BLOCK_START_RE.match(ln) or prev_is_heading or prev_ends_para:
            paras.append([ln])
        else:
            cur.append(ln)
    return "\n\n".join(part for p in paras for part in _split_long(" ".join(p))) + "\n"


# --- Pharmacopoeia / formulary layout ---------------------------------------------
_LEADING_NUM_RE = re.compile(r"^[\d\s:.]+")
PHARMA_BLOCK_CHARS = 1200


def _title_key(line: str) -> str | None:
    """Uppercase monograph-style title (after glyph mapping), else None."""
    s = _LEADING_NUM_RE.sub("", line).strip()
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 4 or len(s) > 70 or not s[0].isalpha() or s.endswith((".", ",", ";")):
        return None
    upper = sum(1 for c in letters if c.isupper())
    return s if upper / len(letters) >= 0.85 else None


def pharmacopoeia_text(pages: list[list[str]], *, max_title_repeats: int = 3) -> str:
    """Keep line layout (ingredient tables); one paragraph per page block, split at
    monograph titles. Uppercase lines that repeat (SYNONYMS, DESCRIPTION, ...) are
    section labels, not titles, and stay inline."""
    title_counts = Counter(k for page in pages for ln in page if (k := _title_key(ln)))
    blocks: list[str] = []

    def flush(buf: list[str]) -> None:
        chunk: list[str] = []
        size = 0
        for ln in buf:
            if chunk and size + len(ln) > PHARMA_BLOCK_CHARS:
                blocks.append("\n".join(chunk))
                chunk, size = [], 0
            chunk.append(ln)
            size += len(ln) + 1
        if chunk:
            blocks.append("\n".join(chunk))

    for page in pages:
        buf: list[str] = []
        for ln in page:
            key = _title_key(ln)
            if key and title_counts[key] <= max_title_repeats:
                flush(buf)
                buf = []
                blocks.append(key)
            else:
                buf.append(ln)
        flush(buf)
    return "\n\n".join(blocks) + "\n"


def clean_pharmacopoeia_pages(pages: list[str], fonts: str) -> tuple[list[list[str]], int]:
    """Glyph mapping + verse removal. Returns (page lines, dropped verse line count)."""
    dropped = 0
    out: list[list[str]] = []
    for lines in strip_page_furniture(pages):
        kept: list[str] = []
        for ln in lines:
            if "B" in fonts:
                ln = " ".join(_KRUTI_SPAN_RE.sub(" ", ln).split())
                if not ln:
                    continue
            if is_devanagari_verse(ln, fonts):
                dropped += 1
                continue
            kept.append(fix_legacy_iast(ln, fonts))
        out.append(kept)
    return out, dropped
