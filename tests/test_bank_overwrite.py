from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.bank_generator.bank_builder import generate_experience_bank
from app.config import AppConfig
from app.llm import OllamaClient


class FakeLLM(OllamaClient):
    def __init__(self):
        super().__init__(base_url="http://fake", model="fake")

    def embed(self, text: str, *, embed_model: str | None = None) -> list[float]:
        return [0.0, 0.0, 0.0]

    def chat(self, system: str, user: str) -> str:
        return "{}"


def test_generate_experience_bank_rejects_overwrite_by_default(tmp_path: Path):
    cfg = AppConfig(data_root=str(tmp_path / "data"))
    llm = FakeLLM()
    resume = r"\\section{EXPERIENCE}\n\\resumeItem{Built a pipeline in Python.}\n"

    r1 = generate_experience_bank(resume_tex=resume, bank_folder_name="bank1", llm=llm, cfg=cfg, overwrite=False)
    assert r1.validation.ok

    r2 = generate_experience_bank(resume_tex=resume, bank_folder_name="bank1", llm=llm, cfg=cfg, overwrite=False)
    assert not r2.validation.ok
    assert any("already exists" in e for e in r2.validation.errors)

