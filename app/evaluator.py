from __future__ import annotations

import json

from app.llm import LLMProvider, redact_large_text
from app.prompts import EVALUATOR_PROMPT, SYSTEM_GUARDRAILS
from app.schemas import EvaluationReport


def evaluate_tailored_resume(*, jd_text: str, tailored_tex: str, llm: LLMProvider) -> EvaluationReport:
    payload = {
        "job_description": redact_large_text(jd_text, limit=9000),
        "tailored_resume_latex": redact_large_text(tailored_tex, limit=12000),
    }
    user = EVALUATOR_PROMPT + "\n\nINPUTS (JSON):\n" + json.dumps(payload, ensure_ascii=False) + "\n"
    return llm.generate_json(system=SYSTEM_GUARDRAILS, user=user, schema=EvaluationReport, max_retries=1, allow_fallback=True)
