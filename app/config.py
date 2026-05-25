from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Literal


@dataclass(frozen=True)
class AppConfig:
    """
    Centralized app configuration.

    Provider selection is environment-driven via `LLM_PROVIDER`.

    Supported providers:
    - `ollama`
    - `openai`
    - `openai_compatible` (any OpenAI API-compatible endpoint, e.g. Hugging Face Inference API)
    """

    llm_provider: Literal["ollama", "openai", "openai_compatible"] = "ollama"
    request_timeout_s: int = 120

    # Ollama
    ollama_base_url: str = "http://localhost:11434"  # env: OLLAMA_HOST
    ollama_model: str = "llama3.2:3b"  # env: OLLAMA_MODEL
    ollama_embedding_model: str = "nomic-embed-text"  # env: OLLAMA_EMBED_MODEL

    # OpenAI
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str | None = None  # env: OPENAI_API_KEY
    openai_model: str = "gpt-4o-mini"  # env: OPENAI_MODEL
    openai_embedding_model: str = "text-embedding-3-small"  # env: OPENAI_EMBED_MODEL

    # OpenAI-compatible (e.g. Hugging Face)
    openai_compatible_base_url: str | None = None  # env: OPENAI_COMPATIBLE_BASE_URL
    openai_compatible_api_key: str | None = None  # env: OPENAI_COMPATIBLE_API_KEY
    openai_compatible_model: str | None = None  # env: OPENAI_COMPATIBLE_MODEL
    openai_compatible_embedding_model: str | None = None  # env: OPENAI_COMPATIBLE_EMBED_MODEL

    # Rewrite / safety defaults
    max_bullet_words: int = 28
    max_keyword_repetition: int = 3
    max_keyword_density: float = 0.25  # fraction of words that are JD keywords
    semantic_drift_warn_ratio: float = 0.45  # difflib ratio; warn if below

    # LaTeX safety
    forbidden_latex_commands: tuple[str, ...] = (
        r"\input",
        r"\include",
        r"\write18",
        r"\openout",
        r"\read",
        r"\catcode",
        r"\usepackage",
        r"\newcommand",
        r"\renewcommand",
    )

    # Experience bank + RAG
    data_root: str = "data"
    qdrant_url: str | None = None  # env: QDRANT_URL
    qdrant_collection: str = "resume_tailor_chunks"  # env: QDRANT_COLLECTION

    @staticmethod
    def from_env(environ: Mapping[str, str] | None = None) -> "AppConfig":
        env = os.environ if environ is None else environ

        def _get(name: str, default: str | None = None) -> str | None:
            v = env.get(name)
            if v is None:
                return default
            v = v.strip()
            return v if v else default

        provider = (_get("LLM_PROVIDER", "ollama") or "ollama").strip()
        if provider not in {"ollama", "openai", "openai_compatible"}:
            provider = "ollama"

        timeout_s_raw = _get("LLM_TIMEOUT_S", None)
        timeout_s = 120
        if timeout_s_raw is not None:
            try:
                timeout_s = int(timeout_s_raw)
            except Exception:
                timeout_s = 120

        return AppConfig(
            llm_provider=provider,  # type: ignore[arg-type]
            request_timeout_s=timeout_s,
            ollama_base_url=_get("OLLAMA_HOST", "http://localhost:11434") or "http://localhost:11434",
            ollama_model=_get("OLLAMA_MODEL", "llama3.2:3b") or "llama3.2:3b",
            ollama_embedding_model=_get("OLLAMA_EMBED_MODEL", "nomic-embed-text") or "nomic-embed-text",
            openai_base_url=_get("OPENAI_BASE_URL", "https://api.openai.com/v1") or "https://api.openai.com/v1",
            openai_api_key=_get("OPENAI_API_KEY", None),
            openai_model=_get("OPENAI_MODEL", "gpt-4o-mini") or "gpt-4o-mini",
            openai_embedding_model=_get("OPENAI_EMBED_MODEL", "text-embedding-3-small") or "text-embedding-3-small",
            openai_compatible_base_url=_get("OPENAI_COMPATIBLE_BASE_URL", None),
            openai_compatible_api_key=_get("OPENAI_COMPATIBLE_API_KEY", None),
            openai_compatible_model=_get("OPENAI_COMPATIBLE_MODEL", None),
            openai_compatible_embedding_model=_get("OPENAI_COMPATIBLE_EMBED_MODEL", None),
            data_root=_get("DATA_ROOT", "data") or "data",
            qdrant_url=_get("QDRANT_URL", None),
            qdrant_collection=_get("QDRANT_COLLECTION", "resume_tailor_chunks") or "resume_tailor_chunks",
        )


DEFAULT_CONFIG = AppConfig.from_env()
