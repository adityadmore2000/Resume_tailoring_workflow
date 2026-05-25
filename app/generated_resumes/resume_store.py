from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.bank_generator.folder_manager import BankFolderError, get_bank_paths, safe_join
from app.config import DEFAULT_CONFIG


class ResumeStoreError(ValueError):
    pass


_RESUME_ID_RE = re.compile(r"^[a-f0-9]{32}$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_resume_id() -> str:
    return uuid.uuid4().hex


def validate_resume_id(resume_id: str) -> None:
    if not isinstance(resume_id, str) or not resume_id:
        raise ResumeStoreError("resume_id is empty.")
    if ".." in resume_id or "/" in resume_id or "\\" in resume_id:
        raise ResumeStoreError("resume_id contains invalid path characters.")
    if not _RESUME_ID_RE.match(resume_id):
        raise ResumeStoreError("resume_id must be a 32-char lowercase hex string.")


@dataclass(frozen=True)
class GeneratedResumePaths:
    bank_folder_name: str
    resume_id: str
    resume_dir: Path
    latex_path: Path
    pdf_path: Path
    markdown_path: Path
    text_path: Path
    traceability_path: Path
    log_path: Path
    meta_path: Path


def get_generated_resume_paths(
    *,
    bank_folder_name: str,
    resume_id: str,
    data_root: Path | None = None,
) -> GeneratedResumePaths:
    data_root = data_root or Path(DEFAULT_CONFIG.data_root)
    # Reuse bank folder validation/slugify rules (prevents traversal).
    paths = get_bank_paths(data_root, bank_folder_name)
    validate_resume_id(resume_id)

    root = data_root / "generated_resumes"
    resume_dir = safe_join(root, paths.bank_folder_name, resume_id)
    return GeneratedResumePaths(
        bank_folder_name=paths.bank_folder_name,
        resume_id=resume_id,
        resume_dir=resume_dir,
        latex_path=resume_dir / "resume.tex",
        pdf_path=resume_dir / "resume.pdf",
        markdown_path=resume_dir / "tailored_resume.md",
        text_path=resume_dir / "tailored_resume.txt",
        traceability_path=resume_dir / "traceability.json",
        log_path=resume_dir / "compile.log",
        meta_path=resume_dir / "metadata.json",
    )


def init_generated_resume(
    *,
    bank_folder_name: str,
    resume_id: str,
    latex: str,
    markdown: str | None = None,
    text: str | None = None,
    traceability: dict | list | None = None,
    data_root: Path | None = None,
) -> GeneratedResumePaths:
    p = get_generated_resume_paths(bank_folder_name=bank_folder_name, resume_id=resume_id, data_root=data_root)
    p.resume_dir.mkdir(parents=True, exist_ok=True)
    p.latex_path.write_text(latex or "", encoding="utf-8")
    if markdown is not None:
        p.markdown_path.write_text(markdown, encoding="utf-8")
    if text is not None:
        p.text_path.write_text(text, encoding="utf-8")
    if traceability is not None:
        p.traceability_path.write_text(json.dumps(traceability, indent=2), encoding="utf-8")
    meta = {
        "resume_id": p.resume_id,
        "bank_folder_name": p.bank_folder_name,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "latex_path": str(p.latex_path),
        "pdf_path": str(p.pdf_path),
        "markdown_path": str(p.markdown_path),
        "text_path": str(p.text_path),
        "traceability_path": str(p.traceability_path),
        "compile_status": "failed",
        "last_compiled_at": None,
    }
    p.meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return p


def read_metadata(paths: GeneratedResumePaths) -> dict:
    if not paths.meta_path.exists():
        return {}
    try:
        return json.loads(paths.meta_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def write_metadata(paths: GeneratedResumePaths, meta: dict) -> None:
    paths.meta_path.parent.mkdir(parents=True, exist_ok=True)
    paths.meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def read_latex(paths: GeneratedResumePaths) -> tuple[str, str]:
    latex = paths.latex_path.read_text(encoding="utf-8", errors="replace") if paths.latex_path.exists() else ""
    meta = read_metadata(paths)
    updated_at = meta.get("updated_at") or ""
    return latex, updated_at


def read_markdown(paths: GeneratedResumePaths) -> str:
    return paths.markdown_path.read_text(encoding="utf-8", errors="replace") if paths.markdown_path.exists() else ""


def read_text(paths: GeneratedResumePaths) -> str:
    return paths.text_path.read_text(encoding="utf-8", errors="replace") if paths.text_path.exists() else ""


def read_traceability(paths: GeneratedResumePaths) -> dict | list:
    if not paths.traceability_path.exists():
        return {}
    try:
        return json.loads(paths.traceability_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def save_latex(paths: GeneratedResumePaths, latex: str) -> str:
    paths.resume_dir.mkdir(parents=True, exist_ok=True)
    paths.latex_path.write_text(latex or "", encoding="utf-8")
    meta = read_metadata(paths)
    if not meta:
        meta = {
            "resume_id": paths.resume_id,
            "bank_folder_name": paths.bank_folder_name,
            "created_at": _now_iso(),
            "latex_path": str(paths.latex_path),
            "pdf_path": str(paths.pdf_path),
            "markdown_path": str(paths.markdown_path),
            "text_path": str(paths.text_path),
            "traceability_path": str(paths.traceability_path),
        }
    meta["updated_at"] = _now_iso()
    write_metadata(paths, meta)
    return meta["updated_at"]


def update_compile_status(
    *,
    paths: GeneratedResumePaths,
    status: str,
    compiled_at: str | None,
) -> dict:
    meta = read_metadata(paths)
    if not meta:
        meta = {
            "resume_id": paths.resume_id,
            "bank_folder_name": paths.bank_folder_name,
            "created_at": _now_iso(),
            "latex_path": str(paths.latex_path),
            "pdf_path": str(paths.pdf_path),
            "markdown_path": str(paths.markdown_path),
            "text_path": str(paths.text_path),
            "traceability_path": str(paths.traceability_path),
        }
    meta["compile_status"] = status
    meta["last_compiled_at"] = compiled_at
    meta["updated_at"] = _now_iso()
    write_metadata(paths, meta)
    return meta
