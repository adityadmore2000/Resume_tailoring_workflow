from __future__ import annotations

from app.llm import OllamaClient, normalize_keyword_list, redact_large_text
from app.prompts import JD_ANALYZER_PROMPT, SYSTEM_GUARDRAILS
from app.schemas import JDAnalysis


def analyze_jd(jd_text: str, llm: OllamaClient) -> JDAnalysis:
    user = (
        JD_ANALYZER_PROMPT
        + "\n\nJOB DESCRIPTION:\n"
        + redact_large_text(jd_text, limit=9000)
        + "\n"
    )
    out = llm.generate_json(system=SYSTEM_GUARDRAILS, user=user, schema=JDAnalysis, max_retries=1, allow_fallback=True)
    out.required_skills = normalize_keyword_list(out.required_skills)
    out.preferred_skills = normalize_keyword_list(out.preferred_skills)
    out.role_focus = normalize_keyword_list(out.role_focus)
    out.important_keywords = normalize_keyword_list(out.important_keywords)
    out.low_priority_keywords = normalize_keyword_list(out.low_priority_keywords)
    out.experience_signals = normalize_keyword_list(out.experience_signals)
    out.deployment_signals = normalize_keyword_list(out.deployment_signals)
    out.rejection_risks = normalize_keyword_list(out.rejection_risks)
    return out
