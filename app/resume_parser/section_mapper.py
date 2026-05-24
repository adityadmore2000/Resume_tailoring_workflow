from __future__ import annotations

from dataclasses import dataclass

from app.schemas import SectionName


@dataclass(frozen=True)
class CanonicalSection:
    canonical_type: str
    original_heading: str


def map_heading_to_canonical(heading: str) -> CanonicalSection:
    # Conservative heuristic mapping; LLM-assisted mapping can be added later.
    h = (heading or "").strip()
    hn = h.casefold()
    if "summary" in hn or "profile" in hn:
        return CanonicalSection(canonical_type="summary", original_heading=h)
    if "experience" in hn or "work" in hn:
        return CanonicalSection(canonical_type="experience", original_heading=h)
    if "project" in hn:
        return CanonicalSection(canonical_type="projects", original_heading=h)
    if "skill" in hn:
        return CanonicalSection(canonical_type="skills", original_heading=h)
    if "education" in hn:
        return CanonicalSection(canonical_type="education", original_heading=h)
    if "cert" in hn:
        return CanonicalSection(canonical_type="certifications", original_heading=h)
    if "publication" in hn:
        return CanonicalSection(canonical_type="publications", original_heading=h)
    if "achievement" in hn or "award" in hn:
        return CanonicalSection(canonical_type="achievements", original_heading=h)
    return CanonicalSection(canonical_type="other", original_heading=h)

