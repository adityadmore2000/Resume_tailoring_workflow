from __future__ import annotations

from dataclasses import dataclass

from app.parser import ParseOptions as _ParseOptions
from app.parser import parse_latex_resume as _parse_latex_resume
from app.schemas import ParsedResume


@dataclass(frozen=True)
class LatexParseResult:
    parsed_resume: ParsedResume


def parse_latex_resume(source_tex: str) -> LatexParseResult:
    # Reuse the existing, span-aware LaTeX parser (supports \item and \resumeItem{...}).
    parsed = _parse_latex_resume(source_tex, options=_ParseOptions())
    return LatexParseResult(parsed_resume=parsed)

