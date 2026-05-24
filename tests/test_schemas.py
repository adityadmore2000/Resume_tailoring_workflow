from __future__ import annotations

from app.schemas import JDAnalysis


def test_jdanalysis_coerces_role_focus_string_to_list():
    jd = JDAnalysis.model_validate({"role_focus": "Python AI Engineer"})
    assert jd.role_focus == ["Python AI Engineer"]

