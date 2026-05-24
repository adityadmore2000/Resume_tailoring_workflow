from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.generated_resumes.resume_store import (
    ResumeStoreError,
    get_generated_resume_paths,
    init_generated_resume,
    new_resume_id,
    read_latex,
    read_markdown,
    read_text,
    read_traceability,
    save_latex,
    validate_resume_id,
)


def test_resume_id_validation_rejects_traversal():
    with pytest.raises(ResumeStoreError):
        validate_resume_id("../evil")
    with pytest.raises(ResumeStoreError):
        validate_resume_id("..")
    with pytest.raises(ResumeStoreError):
        validate_resume_id("abc")  # too short


def test_init_and_save_roundtrip(tmp_path: Path, monkeypatch):
    rid = new_resume_id()
    p = init_generated_resume(
        bank_folder_name="my_bank",
        resume_id=rid,
        latex="\\section{X}\nHi\n",
        markdown="# MD\n",
        text="TXT\n",
        traceability={"items": [{"evidence_ids": ["ev1"]}]},
        data_root=tmp_path,
    )
    assert p.latex_path.exists()
    latex, updated = read_latex(p)
    assert "Hi" in latex

    save_latex(p, latex + "\nMore\n")
    latex2, _ = read_latex(p)
    assert "More" in latex2

    meta = json.loads(p.meta_path.read_text(encoding="utf-8"))
    assert meta["resume_id"] == rid
    assert "markdown_path" in meta and "traceability_path" in meta

    assert read_markdown(p).startswith("# MD")
    assert read_text(p).startswith("TXT")
    assert isinstance(read_traceability(p), dict)


def test_get_generated_resume_paths_scopes_inside_data_root(tmp_path: Path, monkeypatch):
    rid = new_resume_id()
    p = get_generated_resume_paths(bank_folder_name="bank1", resume_id=rid, data_root=tmp_path)
    assert str(p.resume_dir).startswith(str((tmp_path / "generated_resumes").resolve()))
