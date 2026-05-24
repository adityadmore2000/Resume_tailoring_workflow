from __future__ import annotations

from pathlib import Path

import pytest

from app.generated_resumes.latex_compiler import LatexCompileError, compile_resume_latex
from app.generated_resumes.resume_store import init_generated_resume, new_resume_id


def test_compile_fails_cleanly_when_no_compiler(tmp_path: Path, monkeypatch):
    # Force compiler detection to fail.
    import app.generated_resumes.latex_compiler as lc

    monkeypatch.setattr(lc.shutil, "which", lambda _: None)

    rid = new_resume_id()
    paths = init_generated_resume(
        bank_folder_name="b",
        resume_id=rid,
        latex="\\documentclass{article}\\begin{document}Hi\\end{document}",
        data_root=tmp_path,
    )
    with pytest.raises(LatexCompileError):
        compile_resume_latex(paths=paths)


def test_compile_timeout_keeps_last_pdf(tmp_path: Path, monkeypatch):
    # Simulate a timeout and ensure we don't delete existing PDF.
    import app.generated_resumes.latex_compiler as lc

    monkeypatch.setattr(lc.shutil, "which", lambda _: "/usr/bin/pdflatex")

    class _Timeout(Exception):
        pass

    def fake_run(*args, **kwargs):
        raise lc.subprocess.TimeoutExpired(cmd=["pdflatex"], timeout=1, output="x", stderr="y")

    monkeypatch.setattr(lc.subprocess, "run", fake_run)

    rid = new_resume_id()
    paths = init_generated_resume(
        bank_folder_name="b",
        resume_id=rid,
        latex="\\documentclass{article}\\begin{document}Hi\\end{document}",
        data_root=tmp_path,
    )
    # Seed a "last successful" PDF.
    paths.pdf_path.write_bytes(b"%PDF-1.4\\n%fake\\n")
    res = compile_resume_latex(paths=paths, timeout_s=1)
    assert res.status == "failed"
    assert paths.pdf_path.exists()
    assert paths.pdf_path.read_bytes().startswith(b"%PDF")


def test_compile_preflight_applies_safe_fixes_before_running_compiler(tmp_path: Path, monkeypatch):
    import app.generated_resumes.latex_compiler as lc

    # Pretend pdflatex exists.
    monkeypatch.setattr(lc.shutil, "which", lambda name: "/usr/bin/pdflatex" if name == "pdflatex" else None)

    # Fake successful compiler run and seed a PDF file as output.
    def fake_run(cmd, cwd, capture_output, text, timeout, check):
        out_pdf = Path(cwd) / "resume.pdf"
        out_pdf.write_bytes(b"%PDF-1.4\\n%fake\\n")

        class P:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return P()

    monkeypatch.setattr(lc.subprocess, "run", fake_run)

    rid = new_resume_id()
    # Missing \resumeSubHeadingListEnd should be auto-fixed before compile.
    bad = "\\documentclass{article}\n\\begin{document}\n\\resumeSubHeadingListStart\n\\item hi\n\\end{document}\n"
    paths = init_generated_resume(bank_folder_name="b", resume_id=rid, latex=bad, data_root=tmp_path)
    res = compile_resume_latex(paths=paths, timeout_s=2)
    assert res.status == "success"
    # Ensure the fix was written back to resume.tex.
    fixed = paths.latex_path.read_text(encoding="utf-8", errors="replace")
    assert "\\resumeSubHeadingListEnd" in fixed
