"""Domain-term protection for translation: canonical botanical / legal terms are never translated."""

from __future__ import annotations

import re

from knowledge_graph.seed_data import HERBS

STATIC_PROTECTED_TERMS: tuple[str, ...] = (
    "Section 3(d)",
    "Section 3(e)",
    "Section 3(p)",
    "Section 3",
    "Ayurvedic Pharmacopoeia of India",
    "Ayurvedic Pharmacopoeia",
    "Ayurvedic Formulary of India",
    "Biological Diversity Act",
    "Drugs and Cosmetics Act",
    "Patents Act",
    "National Biodiversity Authority",
    "State Biodiversity Board",
    "Formulation Intelligence",
    "Product Review",
    "Patent Advisor",
    "AyurDisha",
    "NBA",
    "ABS",
    "SBB",
    "GMP",
    "FSSAI",
    "AYUSH",
)


def _herb_terms() -> list[str]:
    terms: list[str] = []
    for herb in HERBS:
        terms.append(herb.botanical_name)
        terms.extend(herb.names)
    return terms


def protected_terms(extra: list[str] | None = None) -> list[str]:
    terms = {*STATIC_PROTECTED_TERMS, *_herb_terms(), *(extra or [])}
    return sorted((t for t in terms if t and t.strip()), key=len, reverse=True)


def protect(text: str, extra: list[str] | None = None) -> tuple[str, dict[str, str]]:
    """Replace protected terms with opaque placeholders; returns (masked_text, placeholder->term)."""
    mapping: dict[str, str] = {}
    masked = text
    for term in protected_terms(extra):
        pattern = re.compile(rf"(?<![\w]){re.escape(term)}(?![\w])", re.IGNORECASE)
        if not pattern.search(masked):
            continue
        token = f"ZXQ{len(mapping)}QXZ"
        original = pattern.search(masked).group(0)
        mapping[token] = original
        masked = pattern.sub(token, masked)
    return masked, mapping


def restore(text: str, mapping: dict[str, str]) -> tuple[str, list[str]]:
    """Put protected terms back. Returns (text, lost_terms) — lost when the MT mangled a token."""
    out = text
    lost: list[str] = []
    for token, term in mapping.items():
        pattern = re.compile(re.escape(token), re.IGNORECASE)
        if pattern.search(out):
            out = pattern.sub(term, out)
        else:
            lost.append(term)
    return out, lost
