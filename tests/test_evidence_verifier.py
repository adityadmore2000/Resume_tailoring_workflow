from __future__ import annotations

from app.bank_generator.schemas import ExperienceBankIndex, AtomicEvidenceClaim
from app.schemas import JDAnalysis, MatchStrength
from app.tailoring.evidence_verifier import verify_retrieved_evidence


def test_evidence_verifier_marks_supported_and_missing():
    bank = ExperienceBankIndex(
        bank_folder_name="b",
        source_format="latex",
        sections=[],
        evidence_claims=[
            AtomicEvidenceClaim(
                evidence_id="ev_aaaaaaaaaaaa",
                claim_text="Built a validation pipeline in Python.",
                source_section="Experience",
                source_text="Built a validation pipeline in Python.",
            )
        ],
        work_experience=[],
        projects=[],
        capabilities=[],
        deployments=[],
        metrics=[],
        reusable_bullets=[],
    )
    jd = JDAnalysis(required_skills=["Python"], important_keywords=["Kubernetes"])
    verified, evidence_map = verify_retrieved_evidence(jd=jd, bank_index=bank, retrieved_evidence_ids=["ev_aaaaaaaaaaaa"])

    items = {i.requirement: i.strength for i in evidence_map.items}
    assert items["Python"] == MatchStrength.strong_match
    assert items["Kubernetes"] == MatchStrength.missing
    assert verified

