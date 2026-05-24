from __future__ import annotations

from pathlib import Path

import pytest

from app.generated_resumes.resume_store import init_generated_resume, new_resume_id
from app.ui.api.resumes_api import ResumeAPIError, get_markdown, get_resume_metadata, get_text, get_traceability


def test_resume_api_reads_metadata_and_artifacts(tmp_path: Path):
    rid = new_resume_id()
    p = init_generated_resume(
        bank_folder_name="bankx",
        resume_id=rid,
        latex="\\documentclass{article}\\begin{document}Hi\\end{document}",
        markdown="# md",
        text="txt",
        traceability={"items": [{"evidence_ids": ["ev1"]}]},
        data_root=tmp_path,
    )

    meta = get_resume_metadata(rid, data_root=tmp_path)
    assert meta["resume_id"] == rid
    assert meta["bank_folder_name"] == "bankx"

    assert get_markdown(rid, data_root=tmp_path)["markdown"].startswith("# md")
    assert get_text(rid, data_root=tmp_path)["text"].startswith("txt")
    assert "items" in get_traceability(rid, data_root=tmp_path)["traceability"]


def test_resume_api_rejects_unknown_resume_id(tmp_path: Path):
    with pytest.raises(ResumeAPIError):
        get_resume_metadata("0" * 32, data_root=tmp_path)

