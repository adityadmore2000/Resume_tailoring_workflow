from __future__ import annotations

from app.config import DEFAULT_CONFIG
from app.verifier import latex_to_plain_for_checks, verify_bullet_rewrite


def test_fake_metric_detector_blocks_new_numbers():
    original = "Built a pipeline."
    candidate = "Built a pipeline that improved latency by 30%."
    res = verify_bullet_rewrite(
        original_latex=original,
        original_plain=original,
        candidate_latex=candidate,
        candidate_plain=latex_to_plain_for_checks(candidate),
        jd_keywords=["pipeline", "latency"],
        allowed_tools_and_skills=["Python"],
        cfg=DEFAULT_CONFIG,
    )
    assert res.ok is False
    assert any(f.name == "fake_metrics" and not f.ok for f in res.flags)


def test_latex_safety_blocks_unbalanced_braces():
    original = r"Built a pipeline."
    candidate = r"Built a pipeline with \textbf{Python."
    res = verify_bullet_rewrite(
        original_latex=original,
        original_plain=original,
        candidate_latex=candidate,
        candidate_plain=latex_to_plain_for_checks(candidate),
        jd_keywords=["python"],
        allowed_tools_and_skills=["Python"],
        cfg=DEFAULT_CONFIG,
    )
    assert res.ok is False
    assert any(f.name == "latex_balanced_braces" and not f.ok for f in res.flags)


def test_section_modification_checker_blocks_structural_latex():
    original = "Built a pipeline."
    candidate = r"Built a pipeline.\section{Hacked}"
    res = verify_bullet_rewrite(
        original_latex=original,
        original_plain=original,
        candidate_latex=candidate,
        candidate_plain=latex_to_plain_for_checks(candidate),
        jd_keywords=["pipeline"],
        allowed_tools_and_skills=["Python"],
        cfg=DEFAULT_CONFIG,
    )
    assert res.ok is False
    assert any(f.name == "section_modification" and not f.ok for f in res.flags)
