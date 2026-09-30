"""Chat model factory — NVIDIA NIM primary, Groq fallback."""

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
    - If ``NVIDIA_API_KEY`` is set, returns ``ChatNVIDIA`` (NIM / API Catalog),
      wrapped with ``LLM_FALLBACK_MODELS`` and then Groq (``GROQ_API_KEY``) when configured.
    - If only ``GROQ_API_KEY`` is set, returns Groq on its own.
    - Otherwise returns ``None`` (nodes will raise a clear config error).
    """
    if llm is not None:
        return llm

    cfg = settings or get_settings()
    chain: list[Any] = []

    if cfg.nvidia_api_key:
        from langchain_nvidia_ai_endpoints import ChatNVIDIA
        from langchain_nvidia_ai_endpoints._statics import determine_model

        def _build(model_id: str) -> Any:
            spec = determine_model(model_id)
            thinking = (spec.thinking_param_enable if cfg.llm_thinking else spec.thinking_param_disable) if spec else None
            return ChatNVIDIA(
                model=model_id,
                api_key=cfg.nvidia_api_key,
                base_url=cfg.nvidia_base_url,
                temperature=cfg.llm_temperature,
                max_completion_tokens=cfg.llm_max_tokens,
                model_kwargs=dict(thinking or {}),
            )

        chain.append(_build(cfg.llm_model))
        chain.extend(_build(m) for m in cfg.llm_fallback_models if m != cfg.llm_model)

    if cfg.groq_api_key:
        chain.append(_build_groq(cfg))

    if not chain:
        return None
    primary, *fallbacks = chain
    return primary.with_fallbacks(fallbacks) if fallbacks else primary


def _build_groq(cfg: Settings) -> Any:
    from langchain_openai import ChatOpenAI

    class _ChatGroq(ChatOpenAI):
        # Groq rejects `json_schema` response_format on most models; tool calling works on all.
        def with_structured_output(self, schema: Any = None, *, method: str = "function_calling", **kwargs: Any) -> Any:
            return super().with_structured_output(schema, method=method, **kwargs)

    return _ChatGroq(
        model=cfg.groq_model,
        api_key=cfg.groq_api_key,
        base_url=cfg.groq_base_url,
        temperature=cfg.llm_temperature,
        max_tokens=cfg.llm_max_tokens,
        timeout=cfg.groq_timeout,
        max_retries=0,
    )
