from __future__ import annotations

# Backward-compat shim (older modules import from `app.prompts`).
from app.llm.prompts import (  # noqa: F401
    EVALUATOR_PROMPT,
    JD_ANALYZER_PROMPT,
    PLANNER_PROMPT,
    REWRITE_PROMPT,
    SYSTEM_GUARDRAILS,
)

