from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.config import DEFAULT_CONFIG
from app.generated_resumes.latex_compiler import LatexCompileError, compile_resume_latex
from app.generated_resumes.resume_store import (
    GeneratedResumePaths,
    get_generated_resume_paths,
    read_latex,
    read_markdown,
    read_metadata,
    read_text,
    read_traceability,
    save_latex,
)


class ResumeAPIError(ValueError):
    pass


@dataclass(frozen=True)
class ResumeLatexResponse:
    resume_id: str
    latex: str
    updated_at: str


def _safe_paths_for_resume_id(resume_id: str, *, data_root: Path | None = None) -> GeneratedResumePaths:
    """
    Resolve a resume_id to its on-disk folder.
    We search under `data/generated_resumes/*/<resume_id>/` to avoid trusting any client-provided bank_folder_name.
    """
    data_root = data_root or Path(DEFAULT_CONFIG.data_root)
    root = (data_root / "generated_resumes").resolve()
    if not root.exists():
        raise ResumeAPIError("No generated resumes directory found.")

    # Find the resume directory by scanning one level deep (bank folders).
    for bank_dir in root.iterdir():
        if not bank_dir.is_dir():
            continue
        candidate = (bank_dir / resume_id).resolve()
        if candidate.exists() and candidate.is_dir():
            # Derive bank name from directory; validate using shared rules.
            return get_generated_resume_paths(bank_folder_name=bank_dir.name, resume_id=resume_id, data_root=data_root)
    raise ResumeAPIError("resume_id not found.")


def get_latex(resume_id: str, *, data_root: Path | None = None) -> ResumeLatexResponse:
    paths = _safe_paths_for_resume_id(resume_id, data_root=data_root)
    latex, updated_at = read_latex(paths)
    return ResumeLatexResponse(resume_id=paths.resume_id, latex=latex, updated_at=updated_at)


def put_latex(resume_id: str, latex: str, *, data_root: Path | None = None) -> dict:
    paths = _safe_paths_for_resume_id(resume_id, data_root=data_root)
    updated_at = save_latex(paths, latex)
    return {"resume_id": paths.resume_id, "status": "saved", "updated_at": updated_at}


def compile_latex(resume_id: str, latex: str | None = None, *, data_root: Path | None = None) -> dict:
    paths = _safe_paths_for_resume_id(resume_id, data_root=data_root)
    if latex is not None:
        save_latex(paths, latex)
    try:
        result = compile_resume_latex(paths=paths)
    except LatexCompileError as e:
        raise ResumeAPIError(str(e)) from e
    resp = {
        "resume_id": paths.resume_id,
        "status": result.status,
        "log": result.log,
        "compiled_at": result.compiled_at,
    }
    if result.status == "success":
        resp["pdf_url"] = f"/api/resumes/{paths.resume_id}/pdf"
    else:
        resp["errors"] = "Compilation failed."
        resp["last_successful_pdf_url"] = f"/api/resumes/{paths.resume_id}/pdf"
    return resp


def read_pdf_bytes(resume_id: str, *, data_root: Path | None = None) -> bytes:
    paths = _safe_paths_for_resume_id(resume_id, data_root=data_root)
    if not paths.pdf_path.exists():
        raise ResumeAPIError("PDF not found for this resume_id. Compile first.")
    return paths.pdf_path.read_bytes()


def get_resume_metadata(resume_id: str, *, data_root: Path | None = None) -> dict:
    paths = _safe_paths_for_resume_id(resume_id, data_root=data_root)
    meta = read_metadata(paths)
    if not meta:
        raise ResumeAPIError("metadata.json not found for this resume_id.")
    return meta


def get_markdown(resume_id: str, *, data_root: Path | None = None) -> dict:
    paths = _safe_paths_for_resume_id(resume_id, data_root=data_root)
    return {"resume_id": paths.resume_id, "markdown": read_markdown(paths)}


def get_text(resume_id: str, *, data_root: Path | None = None) -> dict:
    paths = _safe_paths_for_resume_id(resume_id, data_root=data_root)
    return {"resume_id": paths.resume_id, "text": read_text(paths)}


def get_traceability(resume_id: str, *, data_root: Path | None = None) -> dict:
    paths = _safe_paths_for_resume_id(resume_id, data_root=data_root)
    return {"resume_id": paths.resume_id, "traceability": read_traceability(paths)}
