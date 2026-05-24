from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas import ParsedResume


@dataclass(frozen=True)
class DetectedSection:
    heading: str
    span_start: int
    span_end: int


def detect_sections(parsed: ParsedResume) -> list[DetectedSection]:
    """
    Dynamic section detector.
    MVP: uses existing \\section{...} headings already parsed into ParsedResume.sections.
    """
    out: list[DetectedSection] = []
    for s in parsed.sections:
        out.append(DetectedSection(heading=s.title_raw, span_start=s.span_start, span_end=s.span_end))
    if not out:
        out.append(DetectedSection(heading="Other", span_start=0, span_end=len(parsed.source_tex)))
    return out


def looks_like_latex(text: str) -> bool:
    return bool(re.search(r"\\(documentclass|begin\{document\}|section\{)", text))

