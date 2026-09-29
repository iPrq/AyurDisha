"""Shared LLM helpers for structured patent-advisor node calls."""

from __future__ import annotations

import json
import logging
import random
import re
import time
from typing import Any, Callable, TypeVar

import json_repair
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from config import get_settings
from graph.models import RetrievedSource

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R")

_TRANSIENT_RE = re.compile(
    r"\[(429|500|502|503|504)\]|overloaded|temporarily unavailable|rate limit|timed? ?out",
    re.IGNORECASE,
)
_sleep = time.sleep

# Models whose provider rejected structured output (e.g. NIM `guided_json`); skip straight to JSON prompting.
_NO_STRUCTURED_OUTPUT: set[str] = set()


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
                    f"source_url={s.source_url or ''}",
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

    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    key = _model_key(model)
    if key not in _NO_STRUCTURED_OUTPUT:
        try:
            result = _with_retry(lambda: model.with_structured_output(schema).invoke(messages))
            if isinstance(result, schema):
                return result
            if isinstance(result, BaseModel):
                return schema.model_validate(result.model_dump())
            if isinstance(result, dict):
                return schema.model_validate(result)
            raise TypeError(f"Structured LLM returned unsupported type: {type(result)}")
        except Exception as exc:  # noqa: BLE001 - provider-side structured output unavailable
            if is_transient_llm_error(exc):
                raise
            _NO_STRUCTURED_OUTPUT.add(key)
            logger.warning(
                "Structured output failed for %s on %s (%s); using JSON prompting for this model",
                schema.__name__,
                key,
                str(exc).splitlines()[0][:200],
            )
    return _json_prompt_invoke(model, schema, messages)


def _model_key(model: Any) -> str:
    return str(getattr(model, "model", None) or getattr(model, "model_name", None) or type(model).__name__)


def is_transient_llm_error(exc: BaseException) -> bool:
    return bool(_TRANSIENT_RE.search(f"{type(exc).__name__}: {exc}"))


def _with_retry(fn: Callable[[], R]) -> R:
    """Call ``fn``, retrying transient provider errors (429 / 5xx / timeouts) with backoff."""
    retries = max(0, get_settings().llm_max_retries)
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - classified below
            if attempt >= retries or not is_transient_llm_error(exc):
                raise
            delay = min(2 ** (attempt + 1), 20) + random.uniform(0, 1)
            logger.warning(
                "Transient LLM error (%s); retry %d/%d in %.1fs",
                str(exc).splitlines()[0][:120],
                attempt + 1,
                retries,
                delay,
            )
            _sleep(delay)
    raise AssertionError("unreachable")


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _extract_json_object(text: str) -> Any:
    """Parse the first JSON object in a model reply (ignores <think> blocks / code fences)."""
    cleaned = _FENCE_RE.sub("", _THINK_RE.sub("", text or "").strip()).strip()
    try:
        return json.loads(cleaned)
    except ValueError:
        pass
    start = cleaned.find("{")
    if start < 0:
        raise ValueError("model reply contains no JSON object")
    try:
        obj, _ = json.JSONDecoder().raw_decode(cleaned[start:])
        return obj
    except ValueError as exc:
        # Models often emit trailing commas, comments, single quotes, or unquoted keys.
        repaired = json_repair.loads(cleaned[start:])
        if not isinstance(repaired, dict) or not repaired:
            raise exc
        logger.info("Repaired malformed JSON from model (%s)", str(exc)[:120])
        return repaired


def _json_prompt_invoke(model: Any, schema: type[T], messages: list, *, attempts: int = 2) -> T:
    """Fallback: ask for plain JSON matching the schema; validate with Pydantic in Python.

    Validation is exactly as strict as the structured path: anything that does not
    validate against ``schema`` is rejected (retried once with the error, then raised).
    """
    instructions = (
        "Respond with ONLY one JSON object (no prose, no code fences) that validates "
        "against this JSON Schema:\n" + json.dumps(schema.model_json_schema())
    )
    convo = [*messages, HumanMessage(content=instructions)]
    last_error: Exception | None = None
    for _ in range(attempts):
        reply = _with_retry(lambda: model.invoke(convo))
        content = getattr(reply, "content", reply)
        if isinstance(content, list):  # some providers return content parts
            content = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
        try:
            return schema.model_validate(_extract_json_object(str(content)))
        except (ValueError, ValidationError) as exc:
            last_error = exc
            meta = getattr(reply, "response_metadata", {}) or {}
            logger.warning(
                "Invalid %s reply (len=%d, finish_reason=%s, extra_keys=%s): %r",
                schema.__name__,
                len(str(content)),
                meta.get("finish_reason"),
                sorted((getattr(reply, "additional_kwargs", {}) or {}).keys()),
                str(content)[:300],
            )
            convo = [*convo, reply, HumanMessage(
                content=f"That was not valid for the schema: {str(exc)[:500]}. "
                        "Reply again with ONLY the corrected JSON object."
            )]
    raise ValueError(f"LLM did not return valid {schema.__name__} JSON: {last_error}")
