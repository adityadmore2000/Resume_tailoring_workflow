from __future__ import annotations

from app.bank_generator.schemas import CapabilityEntry
from app.schemas import JDAnalysis
from app.tailoring.skill_categorizer import categorize_skills, render_skills_latex


def test_no_relevant_category_is_generated():
    caps = [
        CapabilityEntry(capability_id="c1", name="RAG", evidence_ids=["ev1"]),
        CapabilityEntry(capability_id="c2", name="YOLOv8", evidence_ids=["ev2"]),
        CapabilityEntry(capability_id="c3", name="Pandas", evidence_ids=["ev3"]),
    ]
    cats = categorize_skills(capabilities=caps, used_evidence_ids=["ev1", "ev2", "ev3"], jd=JDAnalysis(required_skills=["RAG"]))
    assert cats
    assert all(c.name.casefold() not in {"relevant", "other", "misc", "additional", "miscellaneous"} for c in cats)
    latex = render_skills_latex(cats)
    assert "Relevant:" not in latex


def test_skills_are_grouped_semantically_and_deduped():
    caps = [
        CapabilityEntry(capability_id="c1", name="YOLOv5", evidence_ids=["ev1"]),
        CapabilityEntry(capability_id="c2", name="YOLOv8", evidence_ids=["ev2"]),
        CapabilityEntry(capability_id="c3", name="RAG", evidence_ids=["ev3"]),
        CapabilityEntry(capability_id="c4", name="Vector Embeddings", evidence_ids=["ev4"]),
        CapabilityEntry(capability_id="c5", name="Pandas", evidence_ids=["ev5"]),
        CapabilityEntry(capability_id="c6", name="Git", evidence_ids=["ev6"]),
        # Duplicate capability name should not appear twice.
        CapabilityEntry(capability_id="c7", name="git", evidence_ids=["ev6"]),
        # Unsupported (no used evidence) should be rejected.
        CapabilityEntry(capability_id="c8", name="Kubernetes", evidence_ids=["ev_missing"]),
    ]
    used = ["ev1", "ev2", "ev3", "ev4", "ev5", "ev6"]
    jd = JDAnalysis(required_skills=["RAG", "YOLOv8"], important_keywords=["Vector Embeddings"])
    cats = categorize_skills(capabilities=caps, used_evidence_ids=used, jd=jd)
    all_skills = [s.name.casefold() for c in cats for s in c.skills]
    assert "kubernetes" not in all_skills
    assert all_skills.count("git") == 1

    # Semantic grouping expectation: YOLO* should end up in a "Computer Vision ..." category.
    cv_cats = [c for c in cats if "vision" in c.name.casefold()]
    assert cv_cats
    cv_skill_names = {s.name for s in cv_cats[0].skills}
    assert "YOLOv8" in cv_skill_names


def test_jd_relevant_categories_appear_first():
    caps = [
        CapabilityEntry(capability_id="c1", name="Pandas", evidence_ids=["ev1"]),
        CapabilityEntry(capability_id="c2", name="RAG", evidence_ids=["ev2"]),
        CapabilityEntry(capability_id="c3", name="Git", evidence_ids=["ev3"]),
    ]
    jd = JDAnalysis(required_skills=["RAG"])
    cats = categorize_skills(capabilities=caps, used_evidence_ids=["ev1", "ev2", "ev3"], jd=jd)
    assert cats
    # First category should have at least one JD-relevant skill.
    assert any(s.jd_relevant for s in cats[0].skills)
    # Once we hit a non-relevant category, there should be no relevant categories after it.
    seen_non_rel = False
    for c in cats:
        has_rel = any(s.jd_relevant for s in c.skills)
        if seen_non_rel:
            assert not has_rel
        if not has_rel:
            seen_non_rel = True


def test_render_escapes_ampersands_without_double_escaping():
    caps = [
        CapabilityEntry(capability_id="c1", name="R&D", evidence_ids=["ev1"]),
        CapabilityEntry(capability_id="c2", name="Computer Vision", evidence_ids=["ev2"]),
    ]
    jd = JDAnalysis(required_skills=["Computer Vision"])
    cats = categorize_skills(capabilities=caps, used_evidence_ids=["ev1", "ev2"], jd=jd)
    latex = render_skills_latex(cats)
    assert "R\\&D" in latex
    assert "R&D" not in latex

    # Existing escaped sequences should remain escaped once.
    caps2 = [CapabilityEntry(capability_id="c3", name="CV \\& DL", evidence_ids=["ev3"])]
    cats2 = categorize_skills(capabilities=caps2, used_evidence_ids=["ev3"], jd=JDAnalysis(required_skills=[]))
    latex2 = render_skills_latex(cats2)
    assert "\\\\&" not in latex2
