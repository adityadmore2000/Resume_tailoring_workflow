from __future__ import annotations

from pathlib import Path

from app.bank_generator.schemas import ExperienceBankIndex, AtomicEvidenceClaim, WorkExperienceEntry
from app.tailoring.evidence_verifier import VerifiedEvidence
from app.schemas import JDAnalysis
from app.tailoring.resume_assembler import assemble_from_bank


def test_assembler_uses_only_evidence_and_records_ids(tmp_path: Path):
    bank_dir = tmp_path / "bank"
    (bank_dir / "metadata").mkdir(parents=True, exist_ok=True)
    # No template files -> should fall back gracefully.

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
        work_experience=[
            WorkExperienceEntry(
                entry_id="work_1",
                company="Example Co",
                title="Engineer",
                date_range="2024-2025",
                location="Remote",
                evidence_ids=["ev_aaaaaaaaaaaa"],
            )
        ],
        projects=[],
        capabilities=[],
        deployments=[],
        metrics=[],
        reusable_bullets=[],
    )
    verified = [
        VerifiedEvidence(
            evidence_id="ev_aaaaaaaaaaaa",
            support="supported",
            matched_terms=["Python"],
            claim_text="Built a validation pipeline in Python.",
            source_text="Built a validation pipeline in Python.",
        )
    ]
    jd = JDAnalysis(required_skills=["Python"])
    assembled = assemble_from_bank(bank_dir=bank_dir, bank_index=bank, verified_evidence=verified, jd=jd)
    assert "Built a validation pipeline in Python" in assembled.latex
    assert assembled.used_evidence_ids == ["ev_aaaaaaaaaaaa"]
    # Deterministic section order
    assert assembled.latex.find("\\section{EXPERIENCE}") < assembled.latex.find("\\section{PROJECTS}") < assembled.latex.find("\\section{SKILLS}")
