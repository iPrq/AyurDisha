"""Branch-scoped evidence retrieval for the formulation map — reuses the shared LegalRetriever.

Each branch queries only its own source types, with canonical botanical names (never translated
vernacular terms), and keeps jurisdiction / legal_scope filters. Results are never merged into one
undifferentiated pool: every source keeps its branch label.
"""

from __future__ import annotations

import logging
from typing import Any

from graph.formulation.models import FormulationContext, IdentityStatus
from graph.models import LegalScope, RetrievedSource
from retrieval.base import LegalRetriever
from retrieval.mock import get_mock_retriever

logger = logging.getLogger(__name__)

# branch -> (source_types, domestic-only)
BRANCH_SOURCE_TYPES: dict[str, tuple[list[str], bool]] = {
    # Ayurvedic Pharmacopoeia / Formulary / classical kosha texts are indexed as prior_art.
    "traditional_knowledge": (["prior_art"], True),
    "regulatory": (["regulation", "statute", "guideline"], True),
    "abs": (["statute", "guideline", "regulation"], True),
    "patent": (["patent", "comparative_ip"], False),
}
BRANCH_TOP_K = 4


def canonical_terms(ctx: FormulationContext, *, with_synonyms: bool = True, max_synonyms: int = 2) -> list[str]:
    """Canonical botanical names first; raw user terms only when identity is unresolved."""
    terms: list[str] = []
    for ing in ctx.ingredients:
        if ing.botanical_name and ing.identity_status in (IdentityStatus.CONFIRMED, IdentityStatus.PROBABLE):
            terms.append(ing.botanical_name)
            if with_synonyms:
                terms.extend(s for s in ing.synonyms[:max_synonyms] if s.lower() != ing.botanical_name.lower())
        elif ing.identity_status != IdentityStatus.AMBIGUOUS:
            terms.append(ing.user_term)
    return list(dict.fromkeys(t for t in terms if t))


def branch_query(branch: str, ctx: FormulationContext) -> str:
    names = " ".join(canonical_terms(ctx))
    form = ctx.dosage_form or ""
    if branch == "traditional_knowledge":
        return f"{names} Ayurvedic pharmacopoeia formulary monograph traditional use"
    if branch == "regulatory":
        return f"Ayurvedic drug {form} licence manufacture sale {names} Drugs and Cosmetics Act"
    if branch == "abs":
        return f"biological resources access benefit sharing Biological Diversity Act {names}"
    return f"{names} {form} herbal composition patent"


def _tag(sources: list[RetrievedSource], branch: str) -> list[tuple[str, RetrievedSource]]:
    return [(branch, s) for s in sources]


def retrieve_formulation_context(
    ctx: FormulationContext, *, retriever: LegalRetriever | None = None
) -> tuple[list[tuple[str, RetrievedSource]], list[str]]:
    """Returns (branch, source) pairs and branches that failed or returned nothing."""
    client = retriever or get_mock_retriever()
    if not canonical_terms(ctx):
        return [], list(BRANCH_SOURCE_TYPES)
    out: list[tuple[str, RetrievedSource]] = []
    empty: list[str] = []
    seen: set[tuple[str, str]] = set()
    for branch, (types, domestic_only) in BRANCH_SOURCE_TYPES.items():
        scopes = [LegalScope.DOMESTIC] if domestic_only else [LegalScope.DOMESTIC, LegalScope.INTERNATIONAL]
        if ctx.legal_scope == LegalScope.INTERNATIONAL and not domestic_only:
            scopes = [LegalScope.INTERNATIONAL, LegalScope.DOMESTIC]
        got: list[RetrievedSource] = []
        for scope in scopes:
            try:
                hits = client.retrieve(
                    branch_query(branch, ctx),
                    jurisdiction=ctx.jurisdiction or "india",
                    legal_scope=scope,
                    top_k=BRANCH_TOP_K,
                    source_types=types,
                )
            except Exception:  # noqa: BLE001 - one failed branch must not sink the map
                logger.warning("formulation retrieval failed branch=%s scope=%s", branch, scope.value, exc_info=True)
                hits = []
            got.extend(hits)
        for src in got:
            key = (branch, src.id)
            if key not in seen:
                seen.add(key)
                out.append((branch, src))
        if not got:
            empty.append(branch)
    return out, empty


def sources_by_branch(pairs: list[tuple[str, RetrievedSource]]) -> dict[str, list[RetrievedSource]]:
    grouped: dict[str, list[RetrievedSource]] = {}
    for branch, src in pairs:
        grouped.setdefault(branch, []).append(src)
    return grouped


def unique_sources(pairs: list[tuple[str, RetrievedSource]]) -> list[RetrievedSource]:
    merged: dict[str, RetrievedSource] = {}
    for _, src in pairs:
        merged.setdefault(src.id, src)
    return list(merged.values())


def summarize_retrieval(pairs: list[tuple[str, RetrievedSource]]) -> dict[str, Any]:
    return {branch: len(srcs) for branch, srcs in sources_by_branch(pairs).items()}
