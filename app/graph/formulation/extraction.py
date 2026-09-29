"""Formulation extraction from free text / documents: structured LLM call + deterministic rules.

Python post-checks drop any ingredient, quantity or claim that does not appear in the source text.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from graph.formulation.models import UNITS
from graph.prompts import FORMULATION_EXTRACT_SYSTEM
from knowledge_graph.seed_data import AMBIGUOUS_NAMES, HERBS
from llm.structured import structured_invoke

logger = logging.getLogger(__name__)


class ExtractedIngredient(BaseModel):
    user_term: str
    quantity: float | None = None
    unit: str | None = None
    plant_part: str | None = None
    source_text: str | None = None


class FormulationExtraction(BaseModel):
    name: str = ""
    ingredients: list[ExtractedIngredient] = Field(default_factory=list)
    dosage_form: str = ""
    route: str = ""
    intended_use: str = ""
    claims: list[str] = Field(default_factory=list)
    target_market: str = ""


class ExtractionOutcome(BaseModel):
    extraction: FormulationExtraction
    method: Literal["llm", "rules", "llm+rules"]
    dropped: list[str] = Field(default_factory=list, description="Items removed as not present in text")


# ---------------------------------------------------------------------------
# Deterministic lexicon (curated seed herbs + KG fixture terms)
# ---------------------------------------------------------------------------


def _build_lexicon() -> list[str]:
    terms: set[str] = set()
    for herb in HERBS:
        terms.add(herb.botanical_name)
        terms.update(herb.names)
    terms.update(AMBIGUOUS_NAMES)
    return sorted(terms, key=len, reverse=True)


HERB_LEXICON: list[str] = _build_lexicon()

DOSAGE_FORMS: dict[str, str] = {
    "capsules": "capsule",
    "capsule": "capsule",
    "tablets": "tablet",
    "tablet": "tablet",
    "vati": "vati",
    "churna": "churna",
    "powder": "powder",
    "syrup": "syrup",
    "decoction": "decoction",
    "kwath": "kwath",
    "taila": "taila",
    "oil": "oil",
    "cream": "cream",
    "ointment": "ointment",
    "gel": "gel",
    "gummies": "gummy",
    "gummy": "gummy",
    "tea": "tea",
    "avaleha": "avaleha",
    "lehyam": "avaleha",
    "arishta": "arishta",
    "asava": "asava",
    "juice": "juice",
    "drops": "drops",
}
ROUTES = ("oral", "topical", "nasal", "transdermal", "ophthalmic")
PLANT_PARTS = ("root", "leaf", "leaves", "stem", "bark", "seed", "fruit", "flower", "rhizome", "whole plant", "resin")

_UNIT_RE = r"(mg|mcg|µg|g|kg|ml|l|%|iu)"
_NUM_RE = r"(\d+(?:\.\d+)?)"
_STOP_AFTER_USE = re.compile(
    r"\s*(?:[.?!;]|,?\s+(?:then|and then|and check|check|can i|could you|please|also)\b).*$",
    re.IGNORECASE | re.DOTALL,
)
_UNKNOWN_STOPWORDS = {
    "of", "the", "a", "an", "and", "in", "each", "per", "dose", "daily", "capsule", "capsules",
    "tablet", "tablets", "extract", "powder", "for", "with", "to", "then", "check", "also", "please",
    "run", "is", "it", "twice", "once", "or", "instead", "now", "total", "each", "day",
}


def _normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    u = unit.lower().replace("µg", "mcg")
    return u if u in UNITS else None


def _split_plant_part(term: str) -> tuple[str, str | None]:
    """'Ashwagandha root' → ('Ashwagandha', 'root'); the normalizer expects the herb name alone."""
    for part in PLANT_PARTS:
        m = re.match(rf"^(.+?)\s+{part}$", term, re.IGNORECASE) or re.match(rf"^{part}\s+(?:of\s+)?(.+)$", term, re.IGNORECASE)
        if m and m.group(1).strip():
            return m.group(1).strip(), "leaf" if part == "leaves" else part
    return term, None


def _quantity_near(text: str, start: int, end: int) -> tuple[float | None, str | None]:
    """Quantity directly before ('500 mg of X') or after ('X 500 mg', 'X (500mg)') a mention."""
    before = text[max(0, start - 24) : start]
    m = re.search(_NUM_RE + r"\s*" + _UNIT_RE + r"\s*(?:of\s+)?$", before, re.IGNORECASE)
    if m:
        return float(m.group(1)), _normalize_unit(m.group(2))
    after = text[end : end + 24]
    m = re.match(r"\s*[\(:\-–]?\s*" + _NUM_RE + r"\s*" + _UNIT_RE + r"\b", after, re.IGNORECASE)
    if m:
        return float(m.group(1)), _normalize_unit(m.group(2))
    return None, None


def _plant_part_near(text: str, start: int, end: int) -> str | None:
    window = text[max(0, start - 20) : end + 20].lower()
    for part in PLANT_PARTS:
        if re.search(rf"\b{part}\b", window):
            return "leaf" if part == "leaves" else part
    return None


def rules_extract(text: str) -> FormulationExtraction:
    src = text or ""
    found: list[ExtractedIngredient] = []
    taken: list[tuple[int, int]] = []

    def _overlaps(a: int, b: int) -> bool:
        return any(a < e and b > s for s, e in taken)

    for term in HERB_LEXICON:
        for m in re.finditer(rf"(?<![\w-]){re.escape(term)}(?![\w-])", src, re.IGNORECASE):
            if _overlaps(m.start(), m.end()):
                continue
            taken.append((m.start(), m.end()))
            qty, unit = _quantity_near(src, m.start(), m.end())
            found.append(
                ExtractedIngredient(
                    user_term=m.group(0),
                    quantity=qty,
                    unit=unit,
                    plant_part=_plant_part_near(src, m.start(), m.end()),
                    source_text=src[max(0, m.start() - 16) : m.end() + 16].strip(),
                )
            )

    # Quantity-anchored terms outside the lexicon, e.g. "300 mg shilajit".
    for m in re.finditer(_NUM_RE + r"\s*" + _UNIT_RE + r"\s+(?:of\s+)?([A-Za-z][A-Za-z\-]{2,30})", src, re.IGNORECASE):
        word = m.group(3)
        if word.lower() in _UNKNOWN_STOPWORDS or word.lower() in DOSAGE_FORMS or _overlaps(m.start(3), m.end(3)):
            continue
        taken.append((m.start(3), m.end(3)))
        found.append(
            ExtractedIngredient(
                user_term=word,
                quantity=float(m.group(1)),
                unit=_normalize_unit(m.group(2)),
                source_text=m.group(0),
            )
        )

    found.sort(key=lambda i: src.lower().find(i.user_term.lower()))

    dosage_form = ""
    for word, canonical in DOSAGE_FORMS.items():
        if re.search(rf"\b{word}\b", src, re.IGNORECASE):
            dosage_form = canonical
            break

    route = next((r for r in ROUTES if re.search(rf"\b{r}\b", src, re.IGNORECASE)), "")

    intended_use = ""
    m = re.search(r"\bfor\s+(?!the\s+(?:patent|abs|review)\b)([^\n]{2,120})", src, re.IGNORECASE)
    if m:
        intended_use = _STOP_AFTER_USE.sub("", m.group(1)).strip(" ,")
        if intended_use.lower().startswith(("my ", "this ", "it", "patent", "abs")):
            intended_use = ""

    name = ""
    m = re.search(r"\b(?:called|named)\s+[\"']?([A-Z][\w\- ]{2,60}?)[\"']?(?:[.,;]|\s+(?:with|for|containing)\b|$)", src)
    if m:
        name = m.group(1).strip()

    return FormulationExtraction(
        name=name,
        ingredients=found,
        dosage_form=dosage_form,
        route=route,
        intended_use=intended_use,
    )


# ---------------------------------------------------------------------------
# Post-validation (anti-fabrication)
# ---------------------------------------------------------------------------


def _num_in_text(value: float, text: str) -> bool:
    candidates = {str(value), f"{value:g}"}
    if float(value).is_integer():
        candidates.add(str(int(value)))
    return any(re.search(rf"(?<![\d.]){re.escape(c)}(?![\d])", text) for c in candidates)


def _term_in_text(term: str, text: str) -> bool:
    t = term.strip().lower()
    if not t:
        return False
    low = text.lower()
    return t in low or (len(t) >= 5 and t[:5] in low)


def validate_against_text(extraction: FormulationExtraction, text: str) -> tuple[FormulationExtraction, list[str]]:
    dropped: list[str] = []
    kept: list[ExtractedIngredient] = []
    seen: set[str] = set()
    for ing in extraction.ingredients:
        term, part = _split_plant_part((ing.user_term or "").strip())
        if part and not ing.plant_part:
            ing.plant_part = part
        ing.user_term = term
        if not _term_in_text(term, text):
            dropped.append(f"ingredient:{term}")
            continue
        if term.lower() in seen:
            continue
        seen.add(term.lower())
        if ing.quantity is not None and not _num_in_text(ing.quantity, text):
            dropped.append(f"quantity:{term}")
            ing.quantity, ing.unit = None, None
        ing.unit = _normalize_unit(ing.unit) if ing.quantity is not None else None
        if ing.plant_part and not _term_in_text(ing.plant_part, text):
            dropped.append(f"plant_part:{term}")
            ing.plant_part = None
        kept.append(ing)
    extraction.ingredients = kept
    claims = []
    for c in extraction.claims:
        words = [w for w in re.findall(r"[a-zA-Z]{4,}", c)]
        if words and sum(_term_in_text(w, text) for w in words) >= max(1, len(words) // 2):
            claims.append(c.strip())
        else:
            dropped.append(f"claim:{c[:40]}")
    extraction.claims = claims
    for field in ("dosage_form", "route", "target_market", "name"):
        val = getattr(extraction, field)
        if val and not _term_in_text(val.split()[0], text):
            dropped.append(f"{field}:{val}")
            setattr(extraction, field, "")
    return extraction, dropped


def extract_formulation(text: str, *, llm: Any | None = None, max_chars: int = 12000) -> ExtractionOutcome:
    """LLM extraction when configured, otherwise deterministic rules; always post-validated."""
    src = (text or "")[:max_chars]
    rules = rules_extract(src)
    if llm is None:
        cleaned, dropped = validate_against_text(rules, src)
        return ExtractionOutcome(extraction=cleaned, method="rules", dropped=dropped)
    try:
        result = structured_invoke(llm, FormulationExtraction, system=FORMULATION_EXTRACT_SYSTEM, user=src)
    except Exception:  # noqa: BLE001 - degrade to deterministic extraction
        logger.warning("formulation LLM extraction failed; using rules", exc_info=True)
        cleaned, dropped = validate_against_text(rules, src)
        return ExtractionOutcome(extraction=cleaned, method="rules", dropped=dropped)
    cleaned, dropped = validate_against_text(result, src)
    method: Literal["llm", "rules", "llm+rules"] = "llm"
    # Fill fields the LLM left empty from deterministic rules (both are text-grounded).
    known = {i.user_term.lower() for i in cleaned.ingredients}
    for ing in rules.ingredients:
        term = ing.user_term.lower()
        if not any(term in k or k in term for k in known):
            cleaned.ingredients.append(ing)
            method = "llm+rules"
    for field in ("dosage_form", "route", "intended_use"):
        if not getattr(cleaned, field) and getattr(rules, field):
            setattr(cleaned, field, getattr(rules, field))
            method = "llm+rules"
    return ExtractionOutcome(extraction=cleaned, method=method, dropped=dropped)
