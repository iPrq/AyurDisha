"""Structured, content-free observability for Formulation Intelligence and the agent.

Never log document text, formulation contents, transcripts or credentials — only metadata.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator

logger = logging.getLogger("ayurdisha.formulation")

_ALLOWED_KEYS = frozenset(
    {
        "event",
        "intent",
        "intents",
        "decoder",
        "workflow",
        "provider",
        "language",
        "language_method",
        "extraction_method",
        "verification",
        "latency_ms",
        "error_type",
        "action_type",
        "action_count",
        "ingredient_count",
        "source_count",
        "fallback",
        "status",
    }
)


def log_event(event: str, **fields: Any) -> None:
    safe = {k: v for k, v in fields.items() if k in _ALLOWED_KEYS and v is not None}
    logger.info("%s %s", event, " ".join(f"{k}={v}" for k, v in sorted(safe.items())))


@contextmanager
def timed(event: str, **fields: Any) -> Iterator[dict[str, Any]]:
    """Log ``event`` with latency and error type; callers may add fields to the yielded dict."""
    extra: dict[str, Any] = dict(fields)
    start = time.perf_counter()
    try:
        yield extra
    except Exception as exc:
        extra["error_type"] = type(exc).__name__
        extra["status"] = "error"
        raise
    finally:
        extra["latency_ms"] = int((time.perf_counter() - start) * 1000)
        extra.setdefault("status", "ok")
        log_event(event, **extra)
