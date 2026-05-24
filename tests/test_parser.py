from __future__ import annotations

from app.parser import parse_latex_resume
from app.schemas import SectionName


def test_parse_extracts_bullets_and_spans():
    tex = r"""
\section{Experience}
\begin{itemize}
  \item Built a pipeline in Python.
  \item Shipped a CLI tool.
\end{itemize}
"""
    parsed = parse_latex_resume(tex)
    assert len(parsed.bullets) == 2
    assert parsed.bullets[0].section == SectionName.experience
    b0 = parsed.bullets[0]
    assert b0.span_start < b0.span_end
    assert tex[b0.span_start : b0.span_end].strip() == b0.latex.strip()


def test_parse_fallback_section_when_no_section_headers():
    tex = r"\begin{itemize}\item Hello\end{itemize}"
    parsed = parse_latex_resume(tex)
    assert parsed.sections
    assert parsed.warnings


def test_parse_extracts_resumeitem_macro_bullets_and_spans():
    tex = r"""
\section{EXPERIENCE}
\resumeItem{Built a pipeline with \textbf{Python}.}
\resumeItem{Shipped a CLI tool.}
"""
    parsed = parse_latex_resume(tex)
    assert len(parsed.bullets) == 2
    b0 = parsed.bullets[0]
    assert b0.latex == r"Built a pipeline with \textbf{Python}."
    assert tex[b0.span_start : b0.span_end] == b0.latex
