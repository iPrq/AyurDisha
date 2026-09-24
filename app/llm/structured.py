"""Shared LLM helpers for structured patent-advisor node calls."""

from __future__ import annotations

import json
from typing import Any, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from graph.models import RetrievedSource

T = TypeVar("T", bound=BaseModel)


class LLMNotConfiguredError(RuntimeError):
    """Raised when a node needs an LLM but none is configured."""


def require_llm(llm: Any | None) -> Any:
    if llm is None:
        raise LLMNotConfiguredError(
            "LLM not configured. Set NVIDIA_API_KEY in .env "
            "(NVIDIA NIM) and restart the server."
        )
    return llm


def format_sources_for_prompt(sources: list[RetrievedSource]) -> str:
    if not sources:
        return "(no retrieved sources)"
    blocks: list[str] = []
    for s in sources:
        blocks.append(
            "\n".join(
                [
                    f"source_id={s.id}",
                    f"title={s.title}",
                    f"section={s.section or ''}",
                    f"jurisdiction={s.jurisdiction or ''}",
                    f"legal_scope={s.legal_scope.value if hasattr(s.legal_scope, 'value') else s.legal_scope}",
                    f"source_type={s.source_type}",
                    f"text={s.text}",
                ]
            )
        )
    return "\n---\n".join(blocks)


def structured_invoke(
    llm: Any,
    schema: type[T],
    *,
    system: str,
    user: str,
) -> T:
    """Invoke chat model with Pydantic structured output."""
    model = require_llm(llm)

    # Injectable callables for tests: llm(schema, system, user) -> BaseModel | dict
    if callable(model) and not hasattr(model, "with_structured_output"):
        raw = model(schema, system, user)
        if isinstance(raw, schema):
            return raw
        if isinstance(raw, BaseModel):
            return schema.model_validate(raw.model_dump())
        if isinstance(raw, dict):
            return schema.model_validate(raw)
        if isinstance(raw, str):
            return schema.model_validate(json.loads(raw))
        raise TypeError(f"Injectable LLM returned unsupported type: {type(raw)}")

    structured = model.with_structured_output(schema)
    result = structured.invoke(
        [
            SystemMessage(content=system),
            HumanMessage(content=user),
        ]
    )
    if isinstance(result, schema):
        return result
    if isinstance(result, BaseModel):
        return schema.model_validate(result.model_dump())
    if isinstance(result, dict):
        return schema.model_validate(result)
    raise TypeError(f"Structured LLM returned unsupported type: {type(result)}")
