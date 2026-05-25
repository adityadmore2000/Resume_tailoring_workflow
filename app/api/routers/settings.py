from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import DEFAULT_CONFIG

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _mask(v: str | None) -> str | None:
    if not v:
        return None
    if len(v) <= 6:
        return "******"
    return v[:2] + "******" + v[-2:]


class SettingsResponse(BaseModel):
    runtime_switching_enabled: bool
    llm_provider: str
    ollama_host: str | None = None
    ollama_model: str | None = None
    ollama_embed_model: str | None = None
    openai_base_url: str | None = None
    openai_api_key_masked: str | None = None
    openai_model: str | None = None
    openai_embed_model: str | None = None
    openai_compatible_base_url: str | None = None
    openai_compatible_api_key_masked: str | None = None
    openai_compatible_model: str | None = None
    openai_compatible_embed_model: str | None = None


@router.get("", response_model=SettingsResponse)
def api_get_settings():
    cfg = DEFAULT_CONFIG
    return SettingsResponse(
        runtime_switching_enabled=False,
        llm_provider=cfg.llm_provider,
        ollama_host=cfg.ollama_base_url,
        ollama_model=cfg.ollama_model,
        ollama_embed_model=cfg.ollama_embedding_model,
        openai_base_url=cfg.openai_base_url,
        openai_api_key_masked=_mask(cfg.openai_api_key),
        openai_model=cfg.openai_model,
        openai_embed_model=cfg.openai_embedding_model,
        openai_compatible_base_url=cfg.openai_compatible_base_url,
        openai_compatible_api_key_masked=_mask(cfg.openai_compatible_api_key),
        openai_compatible_model=cfg.openai_compatible_model,
        openai_compatible_embed_model=cfg.openai_compatible_embedding_model,
    )


class PutSettingsRequest(BaseModel):
    llm_provider: str
    ollama_host: str | None = None
    ollama_model: str | None = None
    ollama_embed_model: str | None = None
    openai_api_key: str | None = None
    openai_model: str | None = None
    openai_embed_model: str | None = None
    openai_compatible_base_url: str | None = None
    openai_compatible_api_key: str | None = None
    openai_compatible_model: str | None = None
    openai_compatible_embed_model: str | None = None


@router.put("")
def api_put_settings(body: PutSettingsRequest):
    raise HTTPException(
        status_code=409,
        detail="Runtime switching is not enabled yet. Update environment variables and restart the backend.",
    )


class TestResponse(BaseModel):
    ok: bool
    detail: str


@router.post("/test-llm", response_model=TestResponse)
def api_test_llm():
    cfg = DEFAULT_CONFIG
    # Keep this deterministic in tests: validate config shape only.
    if cfg.llm_provider == "ollama":
        if not (cfg.ollama_base_url or "").strip():
            return TestResponse(ok=False, detail="OLLAMA_HOST is empty.")
        return TestResponse(ok=True, detail="Ollama configuration looks valid (connectivity test not executed).")
    if cfg.llm_provider == "openai":
        if not (cfg.openai_api_key or "").strip():
            return TestResponse(ok=False, detail="OPENAI_API_KEY is not set.")
        return TestResponse(ok=True, detail="OpenAI configuration looks valid (connectivity test not executed).")
    if cfg.llm_provider == "openai_compatible":
        if not (cfg.openai_compatible_base_url or "").strip():
            return TestResponse(ok=False, detail="OPENAI_COMPATIBLE_BASE_URL is not set.")
        if not (cfg.openai_compatible_api_key or "").strip():
            return TestResponse(ok=False, detail="OPENAI_COMPATIBLE_API_KEY is not set.")
        return TestResponse(ok=True, detail="OpenAI-compatible configuration looks valid (connectivity test not executed).")
    return TestResponse(ok=False, detail="Unknown provider.")


@router.post("/test-embeddings", response_model=TestResponse)
def api_test_embeddings():
    # Same as /test-llm for now; real connectivity can be added once runtime switching is enabled.
    return api_test_llm()

