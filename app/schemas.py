from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class SectionName(str, Enum):
    summary = "Summary"
    skills = "Skills"
    experience = "Experience"
    projects = "Projects"
    education = "Education"
    other = "Other"


class Bullet(BaseModel):
    id: str
    section: SectionName
    index: int

    latex: str
    plain: str

    # Span of ONLY the bullet content inside the source .tex (excluding "\item ").
    span_start: int
    span_end: int


class ResumeSection(BaseModel):
    name: SectionName
    title_raw: str
    span_start: int
    span_end: int
    bullets: list[Bullet] = Field(default_factory=list)
    raw_text: str = ""


class ParsedResume(BaseModel):
    source_tex: str
    sections: list[ResumeSection]
    bullets: list[Bullet]
    extracted_tools: list[str] = Field(default_factory=list)
    extracted_skills: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class JDAnalysis(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    role_focus: list[str] = Field(default_factory=list)
    important_keywords: list[str] = Field(default_factory=list)
    low_priority_keywords: list[str] = Field(default_factory=list)
    experience_signals: list[str] = Field(default_factory=list)
    deployment_signals: list[str] = Field(default_factory=list)
    rejection_risks: list[str] = Field(default_factory=list)

    @staticmethod
    def _coerce_list(v: Any) -> list[str]:
        # Ollama models sometimes emit a scalar where a list is expected.
        if v is None:
            return []
        if isinstance(v, str):
            v = v.strip()
            return [v] if v else []
        if isinstance(v, (tuple, set)):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, list):
            out: list[str] = []
            for x in v:
                if x is None:
                    continue
                s = str(x).strip()
                if s:
                    out.append(s)
            return out
        # Unknown shape (e.g., dict) -> drop rather than guessing.
        return []

    @field_validator(
        "required_skills",
        "preferred_skills",
        "role_focus",
        "important_keywords",
        "low_priority_keywords",
        "experience_signals",
        "deployment_signals",
        "rejection_risks",
        mode="before",
    )
    @classmethod
    def _fix_list_fields(cls, v: Any) -> list[str]:
        return cls._coerce_list(v)


class MatchStrength(str, Enum):
    strong_match = "strong_match"
    partial_match = "partial_match"
    missing = "missing"


class EvidenceItem(BaseModel):
    requirement: str
    strength: MatchStrength
    evidence_bullet_ids: list[str] = Field(default_factory=list)
    evidence_snippets: list[str] = Field(default_factory=list)


class EvidenceMap(BaseModel):
    items: list[EvidenceItem] = Field(default_factory=list)


class RewriteAction(str, Enum):
    keep = "keep"
    rewrite = "rewrite"
    remove = "remove"


class PlannedChange(BaseModel):
    target_type: Literal["bullet"] = "bullet"
    bullet_id: str
    action: RewriteAction
    reason: str
    priority: int = Field(ge=1, le=5, default=3)


class RewritePlan(BaseModel):
    changes: list[PlannedChange] = Field(default_factory=list)
    reorder_bullet_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SuggestionStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    risky = "risky"
    unsupported = "unsupported"


class VerificationFlag(BaseModel):
    name: str
    ok: bool
    detail: str = ""


class RewriteSuggestion(BaseModel):
    bullet_id: str
    original_latex: str
    suggested_latex: str | None = None
    action: RewriteAction
    reason: str
    flags: list[VerificationFlag] = Field(default_factory=list)
    status: SuggestionStatus = SuggestionStatus.pending
    rejection_reason: str | None = None


class ChangeReport(BaseModel):
    summary: dict[str, Any] = Field(default_factory=dict)
    suggestions: list[RewriteSuggestion] = Field(default_factory=list)
    kept_original_bullets: list[str] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)


class ATSDecision(str, Enum):
    shortlisted = "SHORTLISTED"
    rejected = "REJECTED"


class EvaluationReport(BaseModel):
    # Evaluator output is inherently model-generated; keep defaults + coercion to avoid app crashes.
    ats_match_score: int = Field(default=0, ge=0, le=100)
    decision: ATSDecision = ATSDecision.rejected
    recruiter_impression: str = "Not provided."
    strongest_signals: list[str] = Field(default_factory=list)
    weakest_signals: list[str] = Field(default_factory=list)
    keyword_match_reality: str = "Not provided."
    human_readability_verdict: str = "Not provided."
    unnecessary_or_weak_content_remaining: list[str] = Field(default_factory=list)

    @staticmethod
    def _coerce_str(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, str):
            return v.strip()
        if isinstance(v, dict):
            # Preserve info by flattening.
            parts = []
            for k, val in v.items():
                ks = str(k).strip()
                vs = str(val).strip()
                if ks and vs:
                    parts.append(f"{ks}: {vs}")
                elif ks:
                    parts.append(ks)
            return "; ".join(parts).strip()
        return str(v).strip()

    @staticmethod
    def _coerce_list(v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            s = v.strip()
            s_cf = s.casefold()
            if s_cf in {"", "none", "null", "n/a", "na"}:
                return []
            return [s]
        if isinstance(v, dict):
            return [f"{str(k).strip()}: {str(val).strip()}".strip(": ").strip() for k, val in v.items() if str(k).strip() or str(val).strip()]
        if isinstance(v, (tuple, set)):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, list):
            out: list[str] = []
            for x in v:
                if x is None:
                    continue
                s = str(x).strip()
                if s and s.casefold() not in {"none", "null", "n/a", "na"}:
                    out.append(s)
            return out
        s = str(v).strip()
        return [s] if s else []

    @field_validator("ats_match_score", mode="before")
    @classmethod
    def _fix_score(cls, v: Any) -> int:
        try:
            n = int(float(v))
        except Exception:
            n = 0
        return min(100, max(0, n))

    @field_validator("keyword_match_reality", "recruiter_impression", "human_readability_verdict", mode="before")
    @classmethod
    def _fix_strings(cls, v: Any) -> str:
        return cls._coerce_str(v)

    @field_validator("strongest_signals", "weakest_signals", "unnecessary_or_weak_content_remaining", mode="before")
    @classmethod
    def _fix_lists(cls, v: Any) -> list[str]:
        return cls._coerce_list(v)


class PipelineArtifacts(BaseModel):
    jd_analysis: JDAnalysis
    evidence_map: EvidenceMap
    rewrite_plan: RewritePlan


class PipelineResult(BaseModel):
    tailored_tex: str
    change_report: ChangeReport
    evaluation_report: EvaluationReport | None = None
    artifacts: PipelineArtifacts
