"""Shared Botanical Normalizer — KG-first, then NVIDIA NIM structured LLM."""

from __future__ import annotations

from typing import Any

from config import Settings, get_settings
from graph.models import BotanicalResult, BotanicalStatus
from graph.prompts import BOTANICAL_SYSTEM
from graph.state import PatentAdvisorState
from knowledge_graph.base import BotanicalKnowledgeGraph
from knowledge_graph.mock import get_mock_botanical_kg
from llm.provider import get_chat_model
from llm.structured import structured_invoke


def _resolve_input_term(state: PatentAdvisorState) -> str:
    botanical_input = state.get("botanical_input")
    if isinstance(botanical_input, str) and botanical_input.strip():
        return botanical_input.strip()

    ingredients = state.get("ingredients") or []
    if ingredients:
        first = ingredients[0]
        if isinstance(first, str) and first.strip():
            return first.strip()

    product = state.get("product") or ""
    return product.strip()


def _llm_normalize(term: str, *, llm: Any, kg_hint: str) -> BotanicalResult:
    user = (
        f"Normalize this botanical / ingredient term: {term!r}\n\n"
        f"Knowledge-graph lookup hint:\n{kg_hint}\n\n"
        "Return BotanicalResult. If ambiguous, status=AMBIGUOUS with candidates "
        "and botanical_name=null. Never invent taxa."
    )
    result = structured_invoke(
        llm, BotanicalResult, system=BOTANICAL_SYSTEM, user=user
    )
    result.input_term = term
    return result


def normalize_botanical(
    term: str,
    *,
    kg: BotanicalKnowledgeGraph | None = None,
    settings: Settings | None = None,
    llm: Any | None = None,
) -> BotanicalResult:
    """Normalize vernacular names via KG, then NIM LLM when needed."""
    cfg = settings or get_settings()
    graph = kg or get_mock_botanical_kg()
    model = llm if llm is not None else get_chat_model(settings=cfg)
    cleaned = (term or "").strip()

    if not cleaned:
        return BotanicalResult(
            status=BotanicalStatus.UNRESOLVED,
            input_term="",
            confidence=0.0,
            notes="Empty botanical input.",
        )

    candidates = graph.lookup(cleaned)

    if len(candidates) == 1:
        match = candidates[0]
        if match.confidence >= cfg.botanical_confidence_threshold:
            return BotanicalResult(
                status=BotanicalStatus.RESOLVED,
                input_term=cleaned,
                botanical_name=match.botanical_name,
                synonyms=list(match.synonyms),
                phytochemicals=list(match.phytochemicals),
                confidence=match.confidence,
                candidates=[],
                notes="Resolved from knowledge graph.",
            )

    if len(candidates) > 1:
        # Never silently pick — always AMBIGUOUS when KG returns multiple hits.
        notes = "Multiple botanical candidates — human review required; no silent pick."
        if model is not None:
            hint = "\n".join(
                f"- {c.botanical_name} (confidence={c.confidence:.2f}, "
                f"synonyms={c.synonyms})"
                for c in candidates
            )
            try:
                llm_result = _llm_normalize(cleaned, llm=model, kg_hint=hint)
                notes = llm_result.notes or notes
                enriched = llm_result.candidates or list(candidates)
                return BotanicalResult(
                    status=BotanicalStatus.AMBIGUOUS,
                    input_term=cleaned,
                    botanical_name=None,
                    synonyms=[],
                    phytochemicals=[],
                    confidence=max(c.confidence for c in enriched),
                    candidates=list(enriched),
                    notes=notes,
                )
            except Exception:  # noqa: BLE001
                pass
        return BotanicalResult(
            status=BotanicalStatus.AMBIGUOUS,
            input_term=cleaned,
            botanical_name=None,
            synonyms=[],
            phytochemicals=[],
            confidence=max(c.confidence for c in candidates),
            candidates=list(candidates),
            notes=notes,
        )

    # KG miss or low-confidence single hit → LLM required
    hint = (
        "No high-confidence KG match."
        if not candidates
        else f"Low-confidence single hit: {candidates[0].model_dump()}"
    )
    if model is None:
        return BotanicalResult(
            status=BotanicalStatus.UNRESOLVED,
            input_term=cleaned,
            confidence=0.0,
            candidates=list(candidates),
            notes="No knowledge-graph match and LLM not configured (set NVIDIA_API_KEY).",
        )

    try:
        return _llm_normalize(cleaned, llm=model, kg_hint=hint)
    except Exception as exc:  # noqa: BLE001
        return BotanicalResult(
            status=BotanicalStatus.UNRESOLVED,
            input_term=cleaned,
            confidence=0.0,
            notes=f"LLM botanical normalization failed: {exc}",
        )


def botanical_normalizer_node(
    state: PatentAdvisorState,
    *,
    kg: BotanicalKnowledgeGraph | None = None,
    settings: Settings | None = None,
    llm: Any | None = None,
) -> dict[str, Any]:
    term = _resolve_input_term(state)
    result = normalize_botanical(term, kg=kg, settings=settings, llm=llm)

    update: dict[str, Any] = {
        "botanical_input": term,
        "botanical": result,
        "botanical_status": result.status.value,
        "botanical_confidence": result.confidence,
        "botanical_synonyms": list(result.synonyms),
        "phytochemicals": list(result.phytochemicals),
    }
    if result.botanical_name:
        update["botanical_name"] = result.botanical_name

    if result.status == BotanicalStatus.AMBIGUOUS:
        reasons = list(state.get("escalation_reasons") or [])
        if "ambiguous_botanical" not in reasons:
            reasons.append("ambiguous_botanical")
        update["escalation_reasons"] = reasons
        update["verification_status"] = "HUMAN_REVIEW_REQUIRED"

    return update


def make_botanical_normalizer_node(
    *,
    kg: BotanicalKnowledgeGraph | None = None,
    settings: Settings | None = None,
    llm: Any | None = None,
):
    def _node(state: PatentAdvisorState) -> dict[str, Any]:
        return botanical_normalizer_node(state, kg=kg, settings=settings, llm=llm)

    return _node
