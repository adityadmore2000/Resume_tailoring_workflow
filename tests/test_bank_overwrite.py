from __future__ import annotations

from pathlib import Path

import pytest

from app.bank_generator.bank_builder import generate_experience_bank
from app.config import AppConfig


class FakeLLM:
    def generate_text(self, *, system: str, user: str) -> str:  # pragma: no cover
        return "{}"

    def generate_json(self, *, system: str, user: str, schema, max_retries: int = 1, allow_fallback: bool = True):  # pragma: no cover
        return schema.model_validate({})

    def embed_text(self, text: str) -> list[float]:
        return [0.0, 0.0, 0.0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0, 0.0, 0.0] for _ in texts]


def test_generate_experience_bank_rejects_overwrite_by_default(tmp_path: Path):
    cfg = AppConfig(data_root=str(tmp_path / "data"))
    llm = FakeLLM()
    resume = r"\\section{EXPERIENCE}\n\\resumeItem{Built a pipeline in Python.}\n"

    r1 = generate_experience_bank(resume_tex=resume, bank_folder_name="bank1", llm=llm, cfg=cfg, overwrite=False)
    assert r1.validation.ok

    r2 = generate_experience_bank(resume_tex=resume, bank_folder_name="bank1", llm=llm, cfg=cfg, overwrite=False)
    assert not r2.validation.ok
    assert any("already exists" in e for e in r2.validation.errors)
