from __future__ import annotations

import pytest

from app.config import DEFAULT_CONFIG
from app.llm import LLMError
from app.parser import parse_latex_resume
from app.pipeline import PipelineOptions, run_pipeline
from app.schemas import EvaluationReport, JDAnalysis, RewritePlan


class FakeLLM:
    def __init__(self, *, planned_bullet_id: str):
        self._planned_bullet_id = planned_bullet_id

    def generate_text(self, *, system: str, user: str) -> str:  # pragma: no cover
        return "{}"

    def generate_json(self, *, system: str, user: str, schema, max_retries: int = 1, allow_fallback: bool = True):
        if schema.__name__ == "JDAnalysis":
            return JDAnalysis(
                required_skills=["Python"],
                preferred_skills=[],
                role_focus=["LLM systems"],
                important_keywords=["validation"],
                low_priority_keywords=[],
                experience_signals=[],
                deployment_signals=[],
                rejection_risks=[],
            )
        if schema.__name__ == "RewritePlan":
            return RewritePlan.model_validate(
                {
                    "changes": [
                        {
                            "target_type": "bullet",
                            "bullet_id": self._planned_bullet_id,
                            "action": "rewrite",
                            "reason": "Improve clarity and align with JD, without adding claims.",
                            "priority": 3,
                        }
                    ],
                    "reorder_bullet_ids": [],
                    "notes": [],
                }
            )
        if schema.__name__ == "BulletRewriteOut":
            return schema.model_validate({"suggested_latex": "Improved bullet.", "rationale": "clarity"})
        if schema.__name__ == "EvaluationReport":
            return EvaluationReport.model_validate(
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
        raise LLMError(f"Unexpected schema: {schema.__name__}")

    def embed_text(self, text: str) -> list[float]:  # pragma: no cover
        raise LLMError("not used")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover
        raise LLMError("not used")


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
