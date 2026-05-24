from __future__ import annotations

from app.config import AppConfig
from app.llm import LLMError, OllamaProvider, OpenAICompatibleProvider


def build_llm_provider(cfg: AppConfig):
    """
    Build the configured LLM + embeddings provider.

    Raises LLMError with actionable guidance when configuration is incomplete.
    """
    timeout = cfg.request_timeout_s

    if cfg.llm_provider == "ollama":
        return OllamaProvider(
            base_url=cfg.ollama_base_url,
            chat_model=cfg.ollama_model,
            embed_model=cfg.ollama_embedding_model,
            timeout_s=timeout,
        )

    if cfg.llm_provider == "openai":
        if not cfg.openai_api_key:
            raise LLMError("Missing OpenAI API key. Set OPENAI_API_KEY.")
        return OpenAICompatibleProvider(
            base_url=cfg.openai_base_url,
            api_key=cfg.openai_api_key,
            chat_model=cfg.openai_model,
            embed_model=cfg.openai_embedding_model,
            timeout_s=timeout,
        )

    if cfg.llm_provider == "openai_compatible":
        missing: list[str] = []
        if not cfg.openai_compatible_base_url:
            missing.append("OPENAI_COMPATIBLE_BASE_URL")
        if not cfg.openai_compatible_api_key:
            missing.append("OPENAI_COMPATIBLE_API_KEY")
        if not cfg.openai_compatible_model:
            missing.append("OPENAI_COMPATIBLE_MODEL")
        if not cfg.openai_compatible_embedding_model:
            missing.append("OPENAI_COMPATIBLE_EMBED_MODEL")
        if missing:
            raise LLMError("Missing OpenAI-compatible config. Set: " + ", ".join(missing))
        return OpenAICompatibleProvider(
            base_url=cfg.openai_compatible_base_url,
            api_key=cfg.openai_compatible_api_key,
            chat_model=cfg.openai_compatible_model,
            embed_model=cfg.openai_compatible_embedding_model,
            timeout_s=timeout,
        )

    raise LLMError(f"Unknown LLM_PROVIDER: {cfg.llm_provider}")

