from __future__ import annotations

import json

from pydantic import BaseModel, Field

from app.llm import LLMProvider
from app.prompts import REWRITE_PROMPT, SYSTEM_GUARDRAILS


class BulletRewriteOut(BaseModel):
    suggested_latex: str = Field(min_length=1)
    rationale: str = Field(min_length=1, max_length=400)


def rewrite_bullet(
    *,
    bullet_latex: str,
    bullet_plain: str,
    jd_keywords: list[str],
    role_focus: list[str],
    allowed_tools_and_skills: list[str],
    llm: LLMProvider,
) -> BulletRewriteOut:
    payload = {
        "original_bullet_latex": bullet_latex,
        "original_bullet_plain": bullet_plain,
        "role_focus": role_focus[:20],
        "important_keywords": jd_keywords[:50],
        "allowed_tools_and_skills": allowed_tools_and_skills[:300],
    }
    user = REWRITE_PROMPT + "\n\nINPUTS (JSON):\n" + json.dumps(payload, ensure_ascii=False) + "\n"
    # For per-bullet rewrites, do not silently fall back: if the model output is malformed,
    # the pipeline should reject the rewrite and keep the original bullet.
    return llm.generate_json(system=SYSTEM_GUARDRAILS, user=user, schema=BulletRewriteOut, max_retries=1, allow_fallback=False)
