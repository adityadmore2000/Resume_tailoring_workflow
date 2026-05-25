from __future__ import annotations

import importlib
import os
from pathlib import Path


def _reload_config():
    import app.config

    return importlib.reload(app.config)


def test_dotenv_is_loaded_from_cwd_and_os_env_overrides(tmp_path: Path, monkeypatch):
    original_cwd = os.getcwd()
    try:
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("QDRANT_URL=http://from-dotenv:6333\n", encoding="utf-8")

        monkeypatch.delenv("QDRANT_URL", raising=False)
        cfg_mod = _reload_config()
        assert cfg_mod.DEFAULT_CONFIG.qdrant_url == "http://from-dotenv:6333"

        monkeypatch.setenv("QDRANT_URL", "http://from-os:6333")
        cfg_mod = _reload_config()
        assert cfg_mod.DEFAULT_CONFIG.qdrant_url == "http://from-os:6333"
    finally:
        os.chdir(original_cwd)
        _reload_config()

