from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextParseResult:
    raw_text: str
    warnings: list[str]


def parse_plain_text_resume(text: str) -> TextParseResult:
    # Placeholder for future support (PDF-to-text, etc.)
    t = text or ""
    warnings = []
    if not t.strip():
        warnings.append("Resume text is empty.")
    return TextParseResult(raw_text=t, warnings=warnings)

