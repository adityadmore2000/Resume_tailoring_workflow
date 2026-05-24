from __future__ import annotations

import hashlib
import re

from app.bank_generator.schemas import CapabilityEntry, ExperienceBankIndex


def _stable_id(prefix: str, text: str) -> str:
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{h}"


def map_capabilities_from_resume(index: ExperienceBankIndex, *, extracted_skills: list[str]) -> ExperienceBankIndex:
    skills = [s.strip() for s in extracted_skills if s and s.strip()]
    if not skills:
        return index

    # Link evidence IDs where the skill token appears in the claim text.
    claims = index.evidence_claims
    for skill in skills[:250]:
        ev_ids: list[str] = []
        pat = re.compile(rf"(?i)\b{re.escape(skill)}\b")
        for c in claims:
            if pat.search(c.claim_text):
                ev_ids.append(c.evidence_id)
        index.capabilities.append(
            CapabilityEntry(
                capability_id=_stable_id("cap", skill.casefold()),
                name=skill,
                evidence_ids=ev_ids[:50],
                tools=[],
                domains=[],
            )
        )
    return index

