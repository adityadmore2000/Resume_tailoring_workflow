from __future__ import annotations

import re

from app.schemas import EvidenceItem, EvidenceMap, JDAnalysis, MatchStrength, ParsedResume


def _contains(term: str, text: str) -> bool:
    if not term.strip():
        return False
    # Word-ish boundary match, case-insensitive.
    pat = re.compile(rf"(?i)\b{re.escape(term.strip())}\b")
    return bool(pat.search(text))


def map_evidence(jd: JDAnalysis, resume: ParsedResume) -> EvidenceMap:
    resume_text = "\n".join([b.plain for b in resume.bullets]) + "\n" + " ".join(resume.extracted_skills)
    skills_text = " ".join(resume.extracted_skills)

    requirements = []
    requirements.extend(jd.required_skills)
    requirements.extend(jd.preferred_skills)
    requirements.extend(jd.important_keywords)
    requirements = [r.strip() for r in requirements if r.strip()]

    items: list[EvidenceItem] = []
    for req in requirements:
        evidence_ids: list[str] = []
        evidence_snips: list[str] = []

        in_skills = _contains(req, skills_text)
        in_bullets = []
        for b in resume.bullets:
            if _contains(req, b.plain):
                in_bullets.append(b)

        if in_skills:
            strength = MatchStrength.strong_match
        elif in_bullets:
            strength = MatchStrength.partial_match
        else:
            strength = MatchStrength.missing

        if in_bullets:
            for b in in_bullets[:3]:
                evidence_ids.append(b.id)
                evidence_snips.append(b.plain[:160])

        items.append(
            EvidenceItem(
                requirement=req,
                strength=strength,
                evidence_bullet_ids=evidence_ids,
                evidence_snippets=evidence_snips,
            )
        )

    return EvidenceMap(items=items)

