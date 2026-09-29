"""Ingredient identity resolution — a thin adapter over the shared botanical normalizer."""

from __future__ import annotations

from typing import Any

from config import Settings, get_settings
from graph.formulation.models import FormulationIngredient, IdentityStatus
from graph.models import BotanicalResult, BotanicalStatus
from graph.shared.botanical import normalize_botanical
from knowledge_graph.base import BotanicalKnowledgeGraph


def identity_status_for(result: BotanicalResult, settings: Settings | None = None) -> IdentityStatus:
    cfg = settings or get_settings()
    if result.status == BotanicalStatus.AMBIGUOUS:
        return IdentityStatus.AMBIGUOUS
    if result.status == BotanicalStatus.RESOLVED and result.botanical_name:
        if result.confidence >= cfg.botanical_confidence_threshold:
            return IdentityStatus.CONFIRMED
        return IdentityStatus.PROBABLE
    return IdentityStatus.INSUFFICIENT_EVIDENCE


def apply_botanical_result(
    ingredient: FormulationIngredient, result: BotanicalResult, settings: Settings | None = None
) -> FormulationIngredient:
    status = identity_status_for(result, settings)
    ingredient.botanical = result
    ingredient.identity_status = status
    ingredient.identity_notes = result.notes
    ingredient.resolved_by_user = False
    if status in (IdentityStatus.CONFIRMED, IdentityStatus.PROBABLE):
        ingredient.botanical_name = result.botanical_name
        ingredient.normalized_name = result.botanical_name
        ingredient.synonyms = list(result.synonyms)
        ingredient.candidates = []
        ingredient.ingredient_type = "botanical"
    else:
        ingredient.botanical_name = None
        ingredient.normalized_name = None
        ingredient.synonyms = []
        ingredient.candidates = list(result.candidates)
        if status == IdentityStatus.AMBIGUOUS:
            ingredient.ingredient_type = "botanical"
    return ingredient


def resolve_ingredient(
    ingredient: FormulationIngredient,
    *,
    kg: BotanicalKnowledgeGraph | None = None,
    settings: Settings | None = None,
    llm: Any | None = None,
) -> FormulationIngredient:
    """Run the shared normalizer; ambiguity is preserved with candidates, never auto-picked."""
    result = normalize_botanical(ingredient.user_term, kg=kg, settings=settings, llm=llm)
    return apply_botanical_result(ingredient, result, settings)


def resolve_by_user_choice(ingredient: FormulationIngredient, botanical_name: str) -> FormulationIngredient:
    """User picks one of the normalizer's candidates. Names outside the candidate list are rejected."""
    choice = next(
        (c for c in ingredient.candidates if c.botanical_name.lower() == botanical_name.strip().lower()),
        None,
    )
    if choice is None:
        raise ValueError(
            f"{botanical_name!r} is not one of the candidates for {ingredient.user_term!r}."
        )
    ingredient.botanical_name = choice.botanical_name
    ingredient.normalized_name = choice.botanical_name
    ingredient.synonyms = list(choice.synonyms)
    ingredient.identity_status = IdentityStatus.CONFIRMED
    ingredient.resolved_by_user = True
    ingredient.ingredient_type = "botanical"
    ingredient.identity_notes = "Identity selected by the user from normalizer candidates."
    ingredient.botanical = BotanicalResult(
        status=BotanicalStatus.RESOLVED,
        input_term=ingredient.user_term,
        botanical_name=choice.botanical_name,
        synonyms=list(choice.synonyms),
        phytochemicals=list(choice.phytochemicals),
        confidence=choice.confidence,
        notes=ingredient.identity_notes,
    )
    return ingredient


def botanical_results_for_handoff(ingredients: list[FormulationIngredient]) -> list[BotanicalResult]:
    """BotanicalResults for downstream graphs; unresolved entries keep their honest status."""
    out: list[BotanicalResult] = []
    for ing in ingredients:
        if ing.botanical is not None:
            out.append(ing.botanical.model_copy(update={"input_term": ing.user_term}))
        else:
            out.append(
                BotanicalResult(
                    status=BotanicalStatus.UNRESOLVED,
                    input_term=ing.user_term,
                    notes="Not yet resolved in Formulation Intelligence.",
                )
            )
    return out
