"""Legal / patent retrieval node for Patent Advisor."""

from __future__ import annotations

from typing import Any

from graph.models import LegalScope
from graph.state import PatentAdvisorState
from retrieval.base import LegalRetriever
from retrieval.mock import get_mock_retriever

# Keeps product-regulation / ABS chunks out of patent reasoning.
PATENT_SOURCE_TYPES = [
    "statute",
    "guideline",
    "patent",
    "comparative_ip",
    "prior_art",
    "guidance",
]


def _build_query(state: PatentAdvisorState) -> str:
    parts: list[str] = []
    if state.get("botanical_name"):
        parts.append(str(state["botanical_name"]))
    if state.get("botanical_input"):
        parts.append(str(state["botanical_input"]))
    if state.get("product"):
        parts.append(str(state["product"]))
    ingredients = state.get("ingredients") or []
    parts.extend(str(i) for i in ingredients)
    scope = state.get("legal_scope") or "domestic"
    if str(scope).lower() == "international":
        parts.append("comparative international IP patentable subject matter")
    else:
        parts.append("Section 3 patent traditional knowledge")
    return " ".join(parts)


def legal_patent_retrieval_node(
    state: PatentAdvisorState,
    *,
    retriever: LegalRetriever | None = None,
) -> dict[str, Any]:
    client = retriever or get_mock_retriever()
    jurisdiction = state.get("jurisdiction") or "india"
    legal_scope = state.get("legal_scope") or LegalScope.DOMESTIC
    query = _build_query(state)
    sources = client.retrieve(
        query,
        jurisdiction=jurisdiction,
        legal_scope=legal_scope,
        source_types=PATENT_SOURCE_TYPES,
    )

    update: dict[str, Any] = {
        "retrieved_sources": sources,
        "retrieval_insufficient": len(sources) == 0,
    }

    reasons = list(state.get("escalation_reasons") or [])
    scope_val = (
        legal_scope.value if isinstance(legal_scope, LegalScope) else str(legal_scope)
    )
    if len(sources) == 0:
        if scope_val == LegalScope.INTERNATIONAL.value:
            if "insufficient_international_evidence" not in reasons:
                reasons.append("insufficient_international_evidence")
            update["verification_status"] = "HUMAN_REVIEW_REQUIRED"
        else:
            if "missing_evidence" not in reasons:
                reasons.append("missing_evidence")
        update["escalation_reasons"] = reasons

    return update


def make_retrieval_node(*, retriever: LegalRetriever | None = None):
    def _node(state: PatentAdvisorState) -> dict[str, Any]:
        return legal_patent_retrieval_node(state, retriever=retriever)

    return _node
