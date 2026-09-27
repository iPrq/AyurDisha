"""Find an NVIDIA chat model that works for the Patent Advisor. Read-only.

Run from app/:

    uv run python scripts/check_llm.py                 # list chat models your key can use
    uv run python scripts/check_llm.py --test MODEL_ID  # try the app's structured-output call

When a model passes --test, set it in .env:  LLM_MODEL=MODEL_ID
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import get_settings  # noqa: E402


def list_models(cfg) -> None:
    from langchain_nvidia_ai_endpoints import ChatNVIDIA

    models = ChatNVIDIA.get_available_models(api_key=cfg.nvidia_api_key, base_url=cfg.nvidia_base_url)
    chat = [m for m in models if (m.model_type or "chat") == "chat" and not m.deprecated]
    known = sorted(m.id for m in chat if m.supports_structured_output)
    unknown = sorted(m.id for m in chat if m.supports_structured_output is None)
    print(f"Current LLM_MODEL: {cfg.llm_model}\n")
    print("Chat models marked as supporting structured output (best candidates):")
    for mid in known:
        print("   ", mid)
    print(f"\n{len(unknown)} other chat models with unknown structured-output support (may still work).")
    print("\nNext: uv run python scripts/check_llm.py --test <one of the models above>")


SOURCE = ("Retrieved sources:\nsource_id=test-1\nsection=3(k)\n"
          "text=[placeholder test text - not statutory]\n")


def test_model(cfg, model_id: str) -> int:
    """Run every structured schema the Patent Advisor uses, through the app's own helper."""
    from langchain_nvidia_ai_endpoints import ChatNVIDIA

    from graph.models import (
        BotanicalResult, IPRouteAnalysis, PriorArtResult, Section3Results, VerificationResult,
    )
    from llm.structured import structured_invoke

    llm = ChatNVIDIA(model=model_id, api_key=cfg.nvidia_api_key, base_url=cfg.nvidia_base_url,
                     temperature=cfg.llm_temperature)
    cases = [
        (Section3Results, "Return one provision for clause 3(k), triggered=false, "
                          "evidence_source_ids=['test-1'], and a one-line summary."),
        (PriorArtResult, "Summarize prior-art findings from the source; cite test-1."),
        (IPRouteAnalysis, "Give one suggestion per IP route (Patent, Trademark, Design, Trade Secret)."),
        (VerificationResult, "Verify the claim 'placeholder claim' against the source; outcome PASS or FAIL."),
        (BotanicalResult, "Normalize the term 'placeholder herb'; status UNRESOLVED if unknown."),
    ]
    failures = 0
    for schema, task in cases:
        try:
            structured_invoke(llm, schema, system="Use only the source given. Do not invent text.",
                              user=SOURCE + task)
            print(f"  OK   {schema.__name__}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  FAIL {schema.__name__}: {type(exc).__name__}: {str(exc)[:200]}")
    if failures:
        print(f"FAIL {model_id}: {failures}/{len(cases)} schemas failed")
        return 1
    print(f"OK {model_id}: all {len(cases)} schemas work")
    print(f"Set in .env:  LLM_MODEL={model_id}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--test", metavar="MODEL_ID")
    args = p.parse_args()
    cfg = get_settings()
    if not cfg.nvidia_api_key:
        print("NVIDIA_API_KEY is not set in .env")
        return 2
    if args.test:
        return test_model(cfg, args.test)
    list_models(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
