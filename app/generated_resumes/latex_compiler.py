from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.generated_resumes.resume_store import GeneratedResumePaths, update_compile_status
from app.generated_resumes.latex_structure import validate_and_fix_latex_structure


class LatexCompileError(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class CompileResult:
    status: str  # success|failed
    compiled_at: str
    log: str
    pdf_path: Path | None


def _compiler_available() -> tuple[str | None, str | None]:
    latexmk = shutil.which("latexmk")
    pdflatex = shutil.which("pdflatex")
    return latexmk, pdflatex


def compile_resume_latex(
    *,
    paths: GeneratedResumePaths,
    timeout_s: int = 20,
    max_log_chars: int = 12000,
) -> CompileResult:
    """
    Compile `resume.tex` -> `resume.pdf` inside the resume_id directory.

    Security properties:
    - fixed working dir = `paths.resume_dir`
    - fixed file name = resume.tex
    - args passed as list (no shell=True)
    - no user-provided command strings executed
    - no shell escape flags enabled
    """
    latexmk, pdflatex = _compiler_available()
    if not latexmk and not pdflatex:
        raise LatexCompileError("LaTeX compiler not found. Install `latexmk` or `pdflatex`.")

    workdir = paths.resume_dir
    workdir.mkdir(parents=True, exist_ok=True)
    tex_file = paths.latex_path.name  # always "resume.tex"

    # Preflight: validate LaTeX structure and apply safe auto-fixes if possible.
    raw_tex = paths.latex_path.read_text(encoding="utf-8", errors="replace") if paths.latex_path.exists() else ""
    preflight = validate_and_fix_latex_structure(raw_tex)
    # Apply safe auto-fix if available (even when ok=True) so compilation uses the corrected LaTeX.
    if preflight.fixed_tex is not None:
        paths.latex_path.write_text(preflight.fixed_tex, encoding="utf-8")
        raw_tex = preflight.fixed_tex
        if preflight.fixes:
            # Keep a note in the compile log even for successful preflight fixes.
            fix_lines = ["LaTeX preflight auto-fixes:"]
            for f in preflight.fixes:
                at = f" (line {f.line})" if f.line else ""
                fix_lines.append(f"- {f.message}{at}")
            fix_lines.append("")
            existing = paths.log_path.read_text(encoding="utf-8", errors="replace") if paths.log_path.exists() else ""
            paths.log_path.write_text("\n".join(fix_lines) + existing, encoding="utf-8")

    if not preflight.ok:
        # If a safe fixed version exists, save it but still report the issues/fixes in the log.
        if preflight.fixed_tex is not None:
            paths.latex_path.write_text(preflight.fixed_tex, encoding="utf-8")
            raw_tex = preflight.fixed_tex
        err_lines = []
        if preflight.fixes:
            err_lines.append("LaTeX preflight auto-fixes:")
            for f in preflight.fixes:
                at = f" (line {f.line})" if f.line else ""
                err_lines.append(f"- {f.message}{at}")
            err_lines.append("")
        err_lines.append("LaTeX structure validation failed:")
        for e in preflight.errors[:50]:
            at = f" (line {e.line})" if e.line else ""
            err_lines.append(f"- {e.message}{at}")
        log = "\n".join(err_lines)[:max_log_chars]
        paths.log_path.write_text(log, encoding="utf-8")
        update_compile_status(paths=paths, status="failed", compiled_at=_now_iso())
        raise LatexCompileError("Generated LaTeX has unclosed list environments (see compile.log).")

    cmd: list[str]
    if latexmk:
        # latexmk can manage aux files; keep it strict and non-interactive.
        cmd = [
            latexmk,
            "-pdf",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-no-shell-escape",
            tex_file,
        ]
    else:
        cmd = [
            pdflatex,  # type: ignore[arg-type]
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-no-shell-escape",
            tex_file,
        ]

    compiled_at = _now_iso()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        log = (getattr(e, "stdout", "") or "") + "\n" + (getattr(e, "stderr", "") or "")
        log = log[-max_log_chars:]
        paths.log_path.write_text(log, encoding="utf-8")
        update_compile_status(paths=paths, status="failed", compiled_at=compiled_at)
        return CompileResult(status="failed", compiled_at=compiled_at, log=log, pdf_path=paths.pdf_path if paths.pdf_path.exists() else None)

    log = (proc.stdout or "") + "\n" + (proc.stderr or "")
    log = log[-max_log_chars:]
    paths.log_path.write_text(log, encoding="utf-8")

    # Determine success by PDF existence (latexmk/pdflatex return codes vary with warnings).
    pdf_ok = paths.pdf_path.exists() and paths.pdf_path.stat().st_size > 0
    status = "success" if (proc.returncode == 0 and pdf_ok) else "failed"
    update_compile_status(paths=paths, status=status, compiled_at=compiled_at)
    return CompileResult(status=status, compiled_at=compiled_at, log=log, pdf_path=paths.pdf_path if pdf_ok else (paths.pdf_path if paths.pdf_path.exists() else None))
