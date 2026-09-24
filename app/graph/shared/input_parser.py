"""Input parser for Patent Advisor requests."""

from __future__ import annotations

from typing import Any

from graph.state import PatentAdvisorState


def parse_patent_advisor_input(state: PatentAdvisorState) -> dict[str, Any]:
    """Normalize request fields into botanical_input + notes (no legal conclusions)."""
    ingredients = [i.strip() for i in (state.get("ingredients") or []) if i and i.strip()]
    product = (state.get("product") or "").strip()
    user_query = (state.get("user_query") or "").strip()

    botanical_input = (state.get("botanical_input") or "").strip()
    if not botanical_input:
        botanical_input = ingredients[0] if ingredients else product

    notes_parts = []
    if product:
        notes_parts.append(f"product={product}")
    if ingredients:
        notes_parts.append(f"ingredients={', '.join(ingredients)}")
    if user_query:
        notes_parts.append(f"user_query={user_query}")

    return {
        "product": product,
        "ingredients": ingredients,
        "botanical_input": botanical_input,
        "parsed_notes": "; ".join(notes_parts),
        "retry_count": int(state.get("retry_count") or 0),
    }


def input_parser_node(state: PatentAdvisorState) -> dict[str, Any]:
    return parse_patent_advisor_input(state)
