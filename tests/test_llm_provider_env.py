from __future__ import annotations

import pytest

from app.config import AppConfig
from app.llm import LLMError, OllamaProvider, OpenAICompatibleProvider
from app.llm.factory import build_llm_provider


def test_env_selects_ollama_provider():
    cfg = AppConfig.from_env(
        {
            "LLM_PROVIDER": "ollama",
            "OLLAMA_HOST": "http://localhost:11434",
            "OLLAMA_MODEL": "llama3.1:8b",
            "OLLAMA_EMBED_MODEL": "nomic-embed-text",
        }
    )
    p = build_llm_provider(cfg)
    assert isinstance(p, OllamaProvider)
    assert p.base_url == "http://localhost:11434"
    assert p.chat_model == "llama3.1:8b"
    assert p.embed_model == "nomic-embed-text"


def test_env_selects_openai_provider():
    cfg = AppConfig.from_env(
        {
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_MODEL": "gpt-4o-mini",
            "OPENAI_EMBED_MODEL": "text-embedding-3-small",
        }
    )
    p = build_llm_provider(cfg)
    assert isinstance(p, OpenAICompatibleProvider)
    assert p.base_url.startswith("https://")
    assert p.chat_model == "gpt-4o-mini"
    assert p.embed_model == "text-embedding-3-small"


def test_env_selects_openai_compatible_provider():
    cfg = AppConfig.from_env(
        {
            "LLM_PROVIDER": "openai_compatible",
            "OPENAI_COMPATIBLE_BASE_URL": "https://api-inference.huggingface.co/v1",
            "OPENAI_COMPATIBLE_API_KEY": "hf-test",
            "OPENAI_COMPATIBLE_MODEL": "m-chat",
            "OPENAI_COMPATIBLE_EMBED_MODEL": "m-embed",
        }
    )
    p = build_llm_provider(cfg)
    assert isinstance(p, OpenAICompatibleProvider)
    assert p.base_url == "https://api-inference.huggingface.co/v1"
    assert p.chat_model == "m-chat"
    assert p.embed_model == "m-embed"


def test_openai_compatible_missing_vars_fails_cleanly():
    cfg = AppConfig.from_env({"LLM_PROVIDER": "openai_compatible", "OPENAI_COMPATIBLE_BASE_URL": "https://x"})
    with pytest.raises(LLMError) as e:
        build_llm_provider(cfg)
    msg = str(e.value)
    assert "OPENAI_COMPATIBLE_API_KEY" in msg
    assert "OPENAI_COMPATIBLE_MODEL" in msg
    assert "OPENAI_COMPATIBLE_EMBED_MODEL" in msg

