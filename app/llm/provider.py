"""Chat model factory — NVIDIA NIM primary."""

from __future__ import annotations

from typing import Any

from config import Settings, get_settings


def get_chat_model(
    *,
    settings: Settings | None = None,
    llm: Any | None = None,
) -> Any | None:
    """Return a LangChain chat model, or an injected stand-in.

    - If ``llm`` is provided, it is returned as-is (tests inject fakes).
    - If ``NVIDIA_API_KEY`` is set, returns ``ChatNVIDIA`` (NIM / API Catalog).
    - Otherwise returns ``None`` (nodes will raise a clear config error).
    """
    if llm is not None:
        return llm

    cfg = settings or get_settings()
    if not cfg.nvidia_api_key:
        return None

    from langchain_nvidia_ai_endpoints import ChatNVIDIA

    return ChatNVIDIA(
        model=cfg.llm_model,
        api_key=cfg.nvidia_api_key,
        base_url=cfg.nvidia_base_url,
        temperature=cfg.llm_temperature,
    )
