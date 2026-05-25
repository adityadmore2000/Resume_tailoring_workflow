from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi import HTTPException

import app.api.routers.settings as settings_mod
from app.config import DEFAULT_CONFIG


def test_get_settings_masks_api_keys(monkeypatch):
    cfg = replace(DEFAULT_CONFIG, llm_provider="openai", openai_api_key="sk-test-secret")
    monkeypatch.setattr(settings_mod, "DEFAULT_CONFIG", cfg)
    data = settings_mod.api_get_settings()
    assert data.openai_api_key_masked is not None
    assert "sk-test-secret" not in data.openai_api_key_masked


def test_put_settings_returns_restart_required():
    with pytest.raises(HTTPException) as e:
        settings_mod.api_put_settings(settings_mod.PutSettingsRequest(llm_provider="ollama"))
    assert e.value.status_code == 409


def test_test_llm_reports_missing_openai_key(monkeypatch):
    cfg = replace(DEFAULT_CONFIG, llm_provider="openai", openai_api_key=None)
    monkeypatch.setattr(settings_mod, "DEFAULT_CONFIG", cfg)
    res = settings_mod.api_test_llm()
    assert res.ok is False

