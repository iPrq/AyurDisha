"""Server-sent-event streaming of real LangGraph node progress for the existing tool graphs."""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable, Iterator

from pydantic import BaseModel

from llm import is_transient_llm_error

logger = logging.getLogger(__name__)

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

NODE_LABELS: dict[str, dict[str, str]] = {
    "patent_advisor": {
        "input_parser": "Loading formulation",
        "botanical": "Resolving botanical identity",
        "retrieval": "Searching legal and patent evidence",
        "section3": "Running Section 3 analysis",
        "prior_art": "Retrieving prior art",
        "ip_routes": "Assessing IP routes",
        "grant_likelihood": "Estimating grant likelihood",
        "assemble": "Assembling findings",
        "verifier": "Verifying evidence",
    },
    "product_review": {
        "input_parser": "Loading formulation",
        "botanical": "Resolving botanical identities",
        "market_feasibility": "Assessing market feasibility",
        "legal_compliance": "Checking legal compliance",
        "resource_accessibility": "Assessing resource accessibility",
        "aggregate": "Combining dimension ratings",
        "verifier": "Verifying evidence",
    },
    "formulation": {
        "parse_input": "Loading formulation",
        "language_normalization": "Normalizing language",
        "extract_formulation": "Extracting formulation",
        "resolve_botanicals": "Resolving botanical identities",
        "check_ambiguities": "Checking ambiguities",
        "retrieve_context": "Retrieving regulatory, patent and ABS context",
        "characterize_formulation": "Characterizing formulation",
        "build_structured_graph": "Building formulation map",
        "verify_evidence": "Verifying evidence",
        "produce_actions": "Preparing next actions",
    },
    "nba_abs": {
        "input_parser": "Loading formulation",
        "botanical": "Resolving biological resources",
        "applicability": "Assessing biodiversity/ABS applicability",
        "rule_retrieval": "Retrieving benefit-sharing rules",
        "calculation": "Calculating fee (deterministic)",
        "assemble": "Assembling findings",
        "verifier": "Verifying evidence",
    },
}


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def stream_graph(
    graph: Any,
    initial: dict[str, Any],
    *,
    workflow: str,
    to_response: Callable[[dict[str, Any]], BaseModel],
    on_complete: Callable[[BaseModel], None] | None = None,
) -> Iterator[str]:
    """Yield ``step_started`` / ``step_completed`` / ``step_failed`` per real task, then ``result``.

    Steps are emitted only from LangGraph task events — never synthesized.
    """
    labels = NODE_LABELS.get(workflow, {})
    final_state: dict[str, Any] = dict(initial)
    yield sse("run_started", {"workflow": workflow})
    try:
        for mode, chunk in graph.stream(initial, stream_mode=["tasks", "values"]):
            if mode == "values":
                final_state = chunk
                continue
            name = chunk.get("name")
            if not name or name.startswith("__"):
                continue
            label = labels.get(name, name.replace("_", " ").capitalize())
            if "result" in chunk or "error" in chunk:
                if chunk.get("error"):
                    yield sse("step_failed", {"node": name, "label": label, "error": str(chunk["error"])[:300]})
                else:
                    yield sse("step_completed", {"node": name, "label": label})
            else:
                yield sse("step_started", {"node": name, "label": label})
        response = to_response(final_state)
    except Exception as exc:  # noqa: BLE001 - reported to the client as a failed run
        logger.exception("%s stream failed", workflow)
        status = 503 if is_transient_llm_error(exc) else 500
        detail = (
            "The LLM provider is temporarily overloaded. Please retry in a minute."
            if status == 503
            else str(exc)[:500]
        )
        yield sse("error", {"status": status, "detail": detail})
        return
    yield sse("result", response.model_dump(mode="json"))
    if on_complete is not None:
        threading.Thread(target=on_complete, args=(response,), daemon=True).start()
