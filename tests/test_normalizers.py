from __future__ import annotations

from app.normalizers import normalize_evaluation_report, normalize_jd_analysis, normalize_rewrite_plan


def test_normalize_jd_analysis_wraps_string_to_list():
    raw = {"role_focus": "Python AI Engineer", "required_skills": "Python"}
    out = normalize_jd_analysis(raw)
    assert out["role_focus"] == ["Python AI Engineer"]
    assert out["required_skills"] == ["Python"]


def test_normalize_evaluation_report_dict_to_string_and_none_list():
    raw = {
        "ats_match_score": "72",
        "decision": "shortlisted",
        "keyword_match_reality": {"matched": ["python"], "missing": ["mlops"]},
        "unnecessary_or_weak_content_remaining": "None",
    }
    out = normalize_evaluation_report(raw)
    assert out["ats_match_score"] == 72
    assert out["decision"] == "SHORTLISTED"
    assert isinstance(out["keyword_match_reality"], str) and "matched" in out["keyword_match_reality"]
    assert out["unnecessary_or_weak_content_remaining"] == []


def test_normalize_rewrite_plan_handles_single_change_dict():
    raw = {
        "changes": {"bullet_id": "b1", "action": "rewrite", "reason": "align", "priority": "5"},
        "notes": "N/A",
    }
    out = normalize_rewrite_plan(raw)
    assert out["changes"][0]["bullet_id"] == "b1"
    assert out["changes"][0]["priority"] == 5
    assert out["notes"] == []

