from __future__ import annotations

from app.generated_resumes.latex_structure import validate_and_fix_latex_structure


def test_validator_catches_and_fixes_missing_resume_item_list_end():
    tex = "\\documentclass{article}\n\\begin{document}\n\\resumeItemListStart\n\\item hi\n\\end{document}\n"
    res = validate_and_fix_latex_structure(tex)
    assert res.ok
    assert res.fixed_tex is not None
    assert "\\resumeItemListEnd" in res.fixed_tex


def test_validator_catches_and_fixes_missing_resume_subheading_list_end():
    tex = "\\documentclass{article}\n\\begin{document}\n\\resumeSubHeadingListStart\n\\item hi\n\\end{document}\n"
    res = validate_and_fix_latex_structure(tex)
    assert res.ok
    assert res.fixed_tex is not None
    assert "\\resumeSubHeadingListEnd" in res.fixed_tex


def test_validator_catches_and_fixes_unclosed_itemize_before_end_document():
    tex = "\\documentclass{article}\n\\begin{document}\n\\begin{itemize}\n\\item hi\n\\end{document}\n"
    res = validate_and_fix_latex_structure(tex)
    assert res.ok
    assert res.fixed_tex is not None
    assert "\\end{itemize}" in res.fixed_tex

