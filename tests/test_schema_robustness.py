from __future__ import annotations

import json

import pytest

from app.config import DEFAULT_CONFIG
from app.llm import OllamaClient
from app.pipeline import PipelineOptions, run_pipeline
from app.schemas import EvaluationReport, JDAnalysis
from app.verifier import latex_to_plain_for_checks, verify_bullet_rewrite


class FakeLLM(OllamaClient):
    def __init__(self, responses: dict[str, str]):
        super().__init__(base_url="http://fake", model="fake")
        self._responses = responses

    def chat(self, system: str, user: str) -> str:
        for key, resp in self._responses.items():
            if key in user:
                return resp
        return "{}"


def test_generate_json_accepts_code_fenced_json_and_normalizes_lists():
    llm = FakeLLM(
        {
            "Extract job requirements": "```json\n"
            + json.dumps({"role_focus": "Python AI Engineer", "required_skills": ["Python"]})
            + "\n```"
        }
    )
    jd = llm.generate_json(system="x", user="Extract job requirements", schema=JDAnalysis, allow_fallback=True)
    assert jd.role_focus == ["Python AI Engineer"]


def test_generate_json_repairs_trailing_commas():
    llm = FakeLLM(
        {
            "Extract job requirements": "```json\n"
            + '{ "role_focus": ["A"], "required_skills": ["Python",], }\n'
            + "```"
        }
    )
    jd = llm.generate_json(system="x", user="Extract job requirements", schema=JDAnalysis, allow_fallback=True)
    assert jd.required_skills == ["Python"]


def test_evaluation_schema_coerces_dict_and_string_list_fields():
    rep = EvaluationReport.model_validate(
        {
            "ats_match_score": "88",
            "decision": "REJECTED",
            "keyword_match_reality": {"matched": "python"},
            "unnecessary_or_weak_content_remaining": "None",
        }
    )
    assert rep.ats_match_score == 88
    assert isinstance(rep.keyword_match_reality, str)
    assert rep.unnecessary_or_weak_content_remaining == []


def test_evaluation_schema_defaults_when_fields_missing():
    rep = EvaluationReport.model_validate({})
    assert rep.ats_match_score == 0
    assert rep.keyword_match_reality


def test_pipeline_rejects_unsupported_new_tool():
    original = "Built a pipeline in Python."
    candidate = "Built a pipeline in Python and Kubernetes."
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
    assert any(f.name == "tool_hallucination" and not f.ok for f in res.flags)


def test_pipeline_input_validation_empty_jd():
    llm = FakeLLM({})
    with pytest.raises(ValueError):
        run_pipeline(jd_text="", resume_tex="\\section{X}", llm=llm, options=PipelineOptions(run_evaluator=False))


def test_pipeline_input_validation_empty_resume():
    llm = FakeLLM({})
    with pytest.raises(ValueError):
        run_pipeline(jd_text="jd", resume_tex="", llm=llm, options=PipelineOptions(run_evaluator=False))
