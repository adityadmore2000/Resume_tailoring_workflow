from __future__ import annotations

from dataclasses import dataclass

from app.schemas import ParsedResume, RewriteSuggestion, SuggestionStatus


@dataclass(frozen=True)
class Replacement:
    start: int
    end: int
    new_text: str


def rebuild_latex(resume: ParsedResume, suggestions: list[RewriteSuggestion]) -> str:
    """
    Surgical rebuild: replace only the bullet *content* spans (not commands, not structure).
    Replacements are applied from end->start to keep spans stable.
    """
    replacements: list[Replacement] = []
    bullet_by_id = {b.id: b for b in resume.bullets}
    for s in suggestions:
        if s.status != SuggestionStatus.approved:
            continue
        if s.action.value == "rewrite" and s.suggested_latex is not None:
            b = bullet_by_id.get(s.bullet_id)
            if not b:
                continue
            replacements.append(Replacement(start=b.span_start, end=b.span_end, new_text=s.suggested_latex))
        elif s.action.value == "remove":
            # Remove bullet text by blanking it; keep \item structure intact.
            b = bullet_by_id.get(s.bullet_id)
            if not b:
                continue
            replacements.append(Replacement(start=b.span_start, end=b.span_end, new_text=""))

    out = resume.source_tex
    for r in sorted(replacements, key=lambda x: x.start, reverse=True):
        out = out[: r.start] + r.new_text + out[r.end :]
    return out

