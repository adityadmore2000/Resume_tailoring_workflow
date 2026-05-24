from __future__ import annotations

import json

import pytest

from app.config import DEFAULT_CONFIG
from app.llm import OllamaClient
from app.parser import parse_latex_resume
from app.pipeline import PipelineOptions, run_pipeline
from app.schemas import JDAnalysis, RewritePlan


class FakeLLM(OllamaClient):
    def __init__(self, *, planned_bullet_id: str):
        super().__init__(base_url="http://fake", model="fake")
        self._planned_bullet_id = planned_bullet_id

    def chat(self, system: str, user: str) -> str:
        # Route by prompt intent keywords.
        if "Extract job requirements" in user:
            return json.dumps(
                JDAnalysis(
                    required_skills=["Python"],
                    preferred_skills=[],
                    role_focus=["LLM systems"],
                    important_keywords=["validation"],
                    low_priority_keywords=[],
                    experience_signals=[],
                    deployment_signals=[],
                    rejection_risks=[],
                ).model_dump()
            )
        if "You are writing a rewrite plan" in user:
            return json.dumps(
                RewritePlan(
                    changes=[
                        {
                            "target_type": "bullet",
                            "bullet_id": self._planned_bullet_id,
                            "action": "rewrite",
                            "reason": "Improve clarity and align with JD, without adding claims.",
                            "priority": 3,
                        }
                    ],
                    reorder_bullet_ids=[],
                    notes=[],
                ).model_dump()
            )
        if "Rewrite a single resume bullet" in user:
            return json.dumps({"suggested_latex": "Improved bullet.", "rationale": "clarity"})
        if "You are an evaluator" in user:
            return json.dumps(
                {
                    "ats_match_score": 50,
                    "decision": "REJECTED",
                    "recruiter_impression": "ok",
                    "strongest_signals": [],
                    "weakest_signals": [],
                    "keyword_match_reality": "basic",
                    "human_readability_verdict": "fine",
                    "unnecessary_or_weak_content_remaining": [],
                }
            )
        return "{}"


def test_pipeline_runs_without_ollama_by_stubbing_llm():
    resume = r"""
\section{Experience}
\begin{itemize}
  \item Built a pipeline in Python.
\end{itemize}
"""
    parsed = parse_latex_resume(resume)
    llm = FakeLLM(planned_bullet_id=parsed.bullets[0].id)
    jd = "Need Python and validation."
    result = run_pipeline(
        jd_text=jd,
        resume_tex=resume,
        llm=llm,
        cfg=DEFAULT_CONFIG,
        options=PipelineOptions(run_evaluator=True, use_heuristic_planner_on_failure=True, max_rewrites=5),
    )
    assert result.artifacts.jd_analysis.required_skills == ["Python"]
    assert result.change_report.suggestions
