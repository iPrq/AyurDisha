"""Helpers shared by Product Review dimension nodes."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, TypeVar

from pydantic import BaseModel, Field, create_model

from graph.models import (
    BotanicalResult,
    DimensionRating,
    LegalScope,
    RetrievedSource,
    ReviewFinding,
)
from graph.prompts import PRODUCT_DOCUMENT_CONTEXT_HEADER, document_context_block
from llm.structured import structured_invoke
from websearch.base import NO_COUNTRY_BIAS

A = TypeVar("A", bound=BaseModel)


@lru_cache(maxsize=None)
def _draft_schema(schema: type[BaseModel]) -> type[BaseModel]:
    # Defaulted fields read as optional to the LLM, which then skips rating/summary entirely.
    return create_model(
        schema.__name__,
        __base__=schema,
        rating=(
            DimensionRating,
            Field(
                ...,
                description="FAVORABLE, MODERATE or CHALLENGING when the sources support a "
                "judgement; INSUFFICIENT_EVIDENCE only when no source is relevant.",
            ),
        ),
        summary=(
            str,
            Field(..., min_length=1, description="2-4 sentence assessment grounded in the sources."),
        ),
        insufficient_evidence=(
            bool,
            Field(
                default=False,
                description="true only when none of the retrieved sources are relevant.",
            ),
        ),
    )


def invoke_assessment(llm: Any, schema: type[A], *, system: str, user: str) -> A:
    draft = structured_invoke(llm, _draft_schema(schema), system=system, user=user)
    return schema.model_validate(draft.model_dump())


def coerce_scope(value: Any) -> LegalScope:
    if isinstance(value, LegalScope):
        return value
    return LegalScope(str(value or "domestic").lower())


def is_international(state: dict[str, Any]) -> bool:
    return coerce_scope(state.get("legal_scope")) == LegalScope.INTERNATIONAL


def sourcing_region(state: dict[str, Any]) -> str:
    if is_international(state):
        return "global"
    return (state.get("jurisdiction") or "india").strip()


def target_market(state: dict[str, Any]) -> str:
    return (state.get("target_market") or "").strip() or sourcing_region(state)


def search_country(state: dict[str, Any]) -> str | None:
    """Web search geo bias: configured default for Indian scope, none for international."""
    return NO_COUNTRY_BIAS if is_international(state) else None


def resource_names(state: dict[str, Any], limit: int | None = None) -> list[str]:
    """Accepted botanical names where resolved, else the raw ingredient term."""
    botanicals: list[BotanicalResult] = list(state.get("botanicals") or [])
    names = [b.botanical_name or b.input_term for b in botanicals if b.input_term]
    if not names:
        names = [i for i in (state.get("ingredients") or []) if i] or [
            state.get("product") or ""
        ]
    names = [n for n in dict.fromkeys(names) if n]
    return names[:limit] if limit else names


def filter_ids(ids: list[str], valid: set[str]) -> list[str]:
    return [i for i in ids if i in valid]


def sanitize_findings(findings: list[ReviewFinding], valid: set[str]) -> None:
    for finding in findings:
        finding.evidence_source_ids = filter_ids(finding.evidence_source_ids, valid)


def finalize_rating(assessment: Any, cited_ids: list[str]) -> None:
    """A rating with no valid citations is not evidence-backed — force INSUFFICIENT_EVIDENCE."""
    if not cited_ids:
        assessment.insufficient_evidence = True
    if assessment.insufficient_evidence:
        assessment.rating = DimensionRating.INSUFFICIENT_EVIDENCE


def merge_sources(*groups: list[RetrievedSource] | None) -> list[RetrievedSource]:
    merged: dict[str, RetrievedSource] = {}
    for group in groups:
        for src in group or []:
            if src.id not in merged:
                merged[src.id] = src
    return list(merged.values())


def botanical_context(state: dict[str, Any]) -> str:
    lines: list[str] = []
    for b in state.get("botanicals") or []:
        lines.append(
            f"- input={b.input_term!r} status={b.status.value} "
            f"botanical_name={b.botanical_name or 'unresolved'} "
            f"synonyms={b.synonyms} phytochemicals={b.phytochemicals}"
        )
    return "\n".join(lines) or "(no botanical normalization results)"


def product_document_context(state: dict[str, Any]) -> list[str]:
    return document_context_block(
        state.get("document_text"), header=PRODUCT_DOCUMENT_CONTEXT_HEADER
    )
