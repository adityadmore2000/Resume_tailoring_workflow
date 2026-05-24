from __future__ import annotations

import json

from app.llm import LLMProvider
from app.prompts import PLANNER_PROMPT, SYSTEM_GUARDRAILS
from app.schemas import EvidenceMap, JDAnalysis, ParsedResume, RewritePlan


def plan_rewrites(jd: JDAnalysis, resume: ParsedResume, evidence: EvidenceMap, llm: LLMProvider) -> RewritePlan:
    # Keep payload small and structured.
    resume_payload = {
        "bullets": [
            {"id": b.id, "section": b.section.value, "plain": b.plain}
            for b in resume.bullets
        ],
        "skills": resume.extracted_skills[:200],
    }
    evidence_payload = [e.model_dump() for e in evidence.items[:200]]
    jd_payload = jd.model_dump()

    user = (
        PLANNER_PROMPT
        + "\n\nINPUTS (JSON):\n"
        + json.dumps(
            {"jd_analysis": jd_payload, "resume": resume_payload, "evidence": evidence_payload},
            ensure_ascii=False,
        )
        + "\n"
    )
    return llm.generate_json(system=SYSTEM_GUARDRAILS, user=user, schema=RewritePlan, max_retries=1, allow_fallback=True)


def heuristic_plan(jd: JDAnalysis, resume: ParsedResume, evidence: EvidenceMap) -> RewritePlan:
    """
    Conservative fallback: rewrite only bullets that already contain important keywords,
    otherwise keep. Never remove in heuristic mode.
    """
    keywords = {k.casefold() for k in jd.important_keywords + jd.required_skills}
    changes = []
    for b in resume.bullets:
        hit = any(k in b.plain.casefold() for k in keywords if k)
        if hit:
            changes.append(
                {
                    "target_type": "bullet",
                    "bullet_id": b.id,
                    "action": "rewrite",
                    "reason": "Improve clarity and align phrasing with JD keywords already present.",
                    "priority": 3,
                }
            )
        else:
            changes.append(
                {
                    "target_type": "bullet",
                    "bullet_id": b.id,
                    "action": "keep",
                    "reason": "No direct JD alignment opportunity without risking unsupported edits.",
                    "priority": 4,
                }
            )
    return RewritePlan.model_validate({"changes": changes, "reorder_bullet_ids": [], "notes": ["Heuristic fallback plan used."]})
