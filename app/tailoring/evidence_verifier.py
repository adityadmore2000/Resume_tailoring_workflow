from __future__ import annotations

import re
from dataclasses import dataclass

from app.bank_generator.schemas import AtomicEvidenceClaim, ExperienceBankIndex
from app.schemas import EvidenceItem, EvidenceMap, JDAnalysis, MatchStrength


@dataclass(frozen=True)
class VerifiedEvidence:
    evidence_id: str
    support: str  # supported|partially_supported|unsupported
    matched_terms: list[str]
    claim_text: str
    source_text: str


def _term_match(term: str, text: str) -> bool:
    term = (term or "").strip()
    if not term:
        return False
    pat = re.compile(rf"(?i)\b{re.escape(term)}\b")
    return bool(pat.search(text))


def verify_retrieved_evidence(
    *,
    jd: JDAnalysis,
    bank_index: ExperienceBankIndex,
    retrieved_evidence_ids: list[str],
) -> tuple[list[VerifiedEvidence], EvidenceMap]:
    """
    Deterministic verifier for retrieved evidence:
    - Classifies each JD requirement as strong/partial/missing based on evidence claims' claim_text.
    - Produces a list of verified evidence objects for later assembly.
    """
    claim_by_id = {c.evidence_id: c for c in bank_index.evidence_claims}
    retrieved_claims: list[AtomicEvidenceClaim] = [claim_by_id[eid] for eid in retrieved_evidence_ids if eid in claim_by_id]

    requirements = []
    requirements.extend(jd.required_skills)
    requirements.extend(jd.preferred_skills)
    requirements.extend(jd.important_keywords)
    requirements = [r.strip() for r in requirements if r and r.strip()]

    items: list[EvidenceItem] = []

    for req in requirements:
        matching = [c for c in retrieved_claims if _term_match(req, c.claim_text)]
        if matching:
            strength = MatchStrength.strong_match
            evidence_ids = [c.evidence_id for c in matching[:5]]
            snippets = [c.claim_text[:180] for c in matching[:5]]
        else:
            # Consider partial support if any token overlaps (very conservative).
            tokens = [t for t in re.findall(r"[A-Za-z0-9\+\#-]{3,}", req.casefold()) if t]
            partial = []
            for c in retrieved_claims:
                if any(_term_match(t, c.claim_text) for t in tokens):
                    partial.append(c)
            if partial:
                strength = MatchStrength.partial_match
                evidence_ids = [c.evidence_id for c in partial[:5]]
                snippets = [c.claim_text[:180] for c in partial[:5]]
            else:
                strength = MatchStrength.missing
                evidence_ids = []
                snippets = []
        items.append(
            EvidenceItem(
                requirement=req,
                strength=strength,
                evidence_bullet_ids=evidence_ids,
                evidence_snippets=snippets,
            )
        )

    # Verified evidence list for assembly
    verified: list[VerifiedEvidence] = []
    for c in retrieved_claims:
        matched_terms = []
        for t in (jd.required_skills + jd.important_keywords)[:80]:
            if _term_match(t, c.claim_text):
                matched_terms.append(t)
        support = "supported" if matched_terms else "partially_supported"
        verified.append(
            VerifiedEvidence(
                evidence_id=c.evidence_id,
                support=support,
                matched_terms=matched_terms[:10],
                claim_text=c.claim_text,
                source_text=c.source_text,
            )
        )

    return verified, EvidenceMap(items=items)

