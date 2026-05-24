from __future__ import annotations

from pathlib import Path

from app.bank_generator.schemas import ExperienceBankIndex, AtomicEvidenceClaim, WorkExperienceEntry
from app.tailoring.evidence_verifier import VerifiedEvidence
from app.schemas import JDAnalysis
from app.tailoring.resume_assembler import assemble_from_bank, load_bank_index


def test_assembler_includes_summary_and_all_experience_entries_and_order(tmp_path: Path):
    bank_dir = tmp_path / "bank"
    (bank_dir / "metadata").mkdir(parents=True, exist_ok=True)
    # Minimal template markers so assembler uses macro-based rendering.
    (bank_dir / "metadata" / "template_preamble.tex").write_text(
        "\\resumeSubheading\\resumeSubHeadingListStart\\resumeItem{", encoding="utf-8"
    )
    (bank_dir / "metadata" / "template_body_header.tex").write_text("% HEADER\n", encoding="utf-8")
    (bank_dir / "metadata" / "summary_section.tex").write_text("\\section{SUMMARY}\n\\small{Source summary.}\n", encoding="utf-8")
    (bank_dir / "metadata" / "education_section.tex").write_text("\\section{EDUCATION}\n\\small{Source education.}\n", encoding="utf-8")

    bank = ExperienceBankIndex(
        bank_folder_name="b",
        source_format="latex",
        sections=[],
        evidence_claims=[
            AtomicEvidenceClaim(
                evidence_id="ev_nd",
                claim_text="Built a validation pipeline in Python.",
                source_section="Experience",
                source_text="Built a validation pipeline in Python.",
            )
        ],
        work_experience=[
            WorkExperienceEntry(
                entry_id="work_1",
                display_title="AI Engineer $|$ Freelancer",
                subtitle="Computer Vision \\\\& Generative AI Systems Development",
                start_date="07/2024",
                end_date="03/2026",
                location="",
                evidence_ids=["ev_nd"],
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
            evidence_id="ev_nd",
            support="supported",
            matched_terms=["Python"],
            claim_text="Built a validation pipeline in Python.",
            source_text="Built a validation pipeline in Python.",
        )
    ]
    jd = JDAnalysis(required_skills=["Python"])
    assembled = assemble_from_bank(bank_dir=bank_dir, bank_index=bank, verified_evidence=verified, jd=jd)
    assert "Built a validation pipeline in Python" in assembled.latex
    assert assembled.used_evidence_ids == ["ev_nd"]
    # SUMMARY must exist and order is deterministic.
    assert assembled.latex.find("\\section{SUMMARY}") < assembled.latex.find("\\section{EXPERIENCE}") < assembled.latex.find(
        "\\section{PROJECTS}"
    )
    assert assembled.latex.find("\\section{PROJECTS}") < assembled.latex.find("\\section{SKILLS}") < assembled.latex.find(
        "\\section{EDUCATION}"
    )
    # Title/subtitle are preserved (not merged).
    assert "{AI Engineer $|$ Freelancer}" in assembled.latex
    assert "{Computer Vision \\\\& Generative AI Systems Development}" in assembled.latex


def test_assembler_does_not_drop_neilsoft_and_preserves_titles(tmp_path: Path):
    bank_dir = tmp_path / "bank"
    (bank_dir / "metadata").mkdir(parents=True, exist_ok=True)
    (bank_dir / "metadata" / "template_preamble.tex").write_text(
        "\\resumeSubheading\\resumeSubHeadingListStart\\resumeItem{", encoding="utf-8"
    )
    (bank_dir / "metadata" / "template_body_header.tex").write_text("% HEADER\n", encoding="utf-8")
    (bank_dir / "metadata" / "summary_section.tex").write_text("\\section{SUMMARY}\n\\small{Source summary.}\n", encoding="utf-8")
    (bank_dir / "metadata" / "education_section.tex").write_text("\\section{EDUCATION}\n\\small{Source education.}\n", encoding="utf-8")

    bank = ExperienceBankIndex(
        bank_folder_name="b",
        source_format="latex",
        sections=[],
        evidence_claims=[
            AtomicEvidenceClaim(
                evidence_id="ev_nd",
                claim_text="Did React Native work.",
                source_section="Experience",
                source_text="Did React Native work.",
            ),
            AtomicEvidenceClaim(
                evidence_id="ev_free",
                claim_text="Built YOLO pipeline.",
                source_section="Experience",
                source_text="Built YOLO pipeline.",
            ),
            AtomicEvidenceClaim(
                evidence_id="ev_neil",
                claim_text="Built CV pipeline at Neilsoft.",
                source_section="Experience",
                source_text="Built CV pipeline at Neilsoft.",
            ),
        ],
        work_experience=[
            WorkExperienceEntry(
                entry_id="work_nd",
                display_title="Software Engineering Intern $|$ NDSoftTech Solutions",
                subtitle="NDSS Internship",
                start_date="03/2026",
                end_date="05/2026",
                location="Pune, India",
                evidence_ids=["ev_nd"],
            ),
            WorkExperienceEntry(
                entry_id="work_free",
                display_title="AI Engineer $|$ Freelancer",
                subtitle="Computer Vision \\\\& Generative AI Systems Development",
                start_date="07/2024",
                end_date="03/2026",
                location="",
                evidence_ids=["ev_free"],
            ),
            WorkExperienceEntry(
                entry_id="work_neil",
                display_title="AI/ML Engineer $|$ Neilsoft",
                subtitle="Computer Vision Engineering",
                start_date="07/2023",
                end_date="07/2024",
                location="Pune, India",
                evidence_ids=["ev_neil"],
            ),
        ],
        projects=[],
        capabilities=[],
        deployments=[],
        metrics=[],
        reusable_bullets=[],
    )

    # Verified evidence includes only NDSoftTech to simulate JD relevance skew.
    verified = [
        VerifiedEvidence(
            evidence_id="ev_nd",
            support="supported",
            matched_terms=["React Native"],
            claim_text="Did React Native work.",
            source_text="Did React Native work.",
        )
    ]
    jd = JDAnalysis(required_skills=["React Native"])
    assembled = assemble_from_bank(bank_dir=bank_dir, bank_index=bank, verified_evidence=verified, jd=jd)

    # EXPERIENCE must include all entries (including Neilsoft), even if JD relevance is low.
    assert "AI/ML Engineer $|$ Neilsoft" in assembled.latex
    assert "AI Engineer $|$ Freelancer" in assembled.latex
    assert "Software Engineering Intern $|$ NDSoftTech Solutions" in assembled.latex

    # Titles/subtitles are separate and preserved.
    assert "{AI Engineer $|$ Freelancer}" in assembled.latex
    assert "{Computer Vision \\\\& Generative AI Systems Development}" in assembled.latex


def test_load_bank_index_migrates_legacy_work_experience_shape(tmp_path: Path):
    bank_dir = tmp_path / "bank"
    (bank_dir / "metadata").mkdir(parents=True, exist_ok=True)
    legacy = {
        "bank_folder_name": "b",
        "source_format": "latex",
        "sections": [],
        "evidence_claims": [],
        "work_experience": [
            {
                "entry_id": "work_legacy",
                "company": "AI/ML Engineer $|$ Neilsoft",
                "title": "Computer Vision Engineering",
                "date_range": "07/2023 - 07/2024",
                "location": "Pune, India",
                "evidence_ids": ["ev_x"],
            }
        ],
        "projects": [],
        "capabilities": [],
        "deployments": [],
        "metrics": [],
        "reusable_bullets": [],
    }
    (bank_dir / "metadata" / "experience_bank_index.json").write_text(__import__("json").dumps(legacy), encoding="utf-8")
    idx = load_bank_index(bank_dir)
    assert idx.work_experience[0].display_title == "AI/ML Engineer $|$ Neilsoft"
    assert idx.work_experience[0].subtitle == "Computer Vision Engineering"
