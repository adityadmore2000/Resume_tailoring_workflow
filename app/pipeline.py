from __future__ import annotations

from dataclasses import dataclass

from app.config import AppConfig, DEFAULT_CONFIG
from app.evidence_mapper import map_evidence
from app.evaluator import evaluate_tailored_resume
from app.jd_analyzer import analyze_jd
from app.latex_rebuilder import rebuild_latex
from app.llm import LLMError, OllamaClient
from app.parser import parse_latex_resume
from app.planner import heuristic_plan, plan_rewrites
from app.rewriter import rewrite_bullet
from app.schemas import (
    ChangeReport,
    EvidenceMap,
    JDAnalysis,
    ParsedResume,
    PipelineArtifacts,
    PipelineResult,
    RewriteAction,
    RewritePlan,
    RewriteSuggestion,
    SuggestionStatus,
)
from app.verifier import latex_to_plain_for_checks, verify_bullet_rewrite


@dataclass(frozen=True)
class PipelineOptions:
    run_evaluator: bool = True
    use_heuristic_planner_on_failure: bool = True
    max_rewrites: int = 30


def run_pipeline(
    *,
    jd_text: str,
    resume_tex: str,
    llm: OllamaClient,
    cfg: AppConfig = DEFAULT_CONFIG,
    options: PipelineOptions = PipelineOptions(),
    allowed_tools_and_skills_override: list[str] | None = None,
) -> PipelineResult:
    if not jd_text.strip():
        raise ValueError("Job description is empty.")
    if not resume_tex.strip():
        raise ValueError("Resume LaTeX is empty.")

    resume: ParsedResume = parse_latex_resume(resume_tex)
    jd: JDAnalysis = analyze_jd(jd_text, llm)
    evidence: EvidenceMap = map_evidence(jd, resume)
    messages: list[str] = []
    messages.extend(resume.warnings)

    try:
        plan: RewritePlan = plan_rewrites(jd, resume, evidence, llm)
    except LLMError:
        if not options.use_heuristic_planner_on_failure:
            raise
        plan = heuristic_plan(jd, resume, evidence)
        messages.append("Planner returned an unexpected format; used conservative heuristic planner fallback.")

    bullet_by_id = {b.id: b for b in resume.bullets}
    suggestions: list[RewriteSuggestion] = []
    rewrites_used = 0

    jd_keywords = jd.important_keywords + jd.required_skills
    allowed = allowed_tools_and_skills_override or (resume.extracted_skills or resume.extracted_tools)

    for ch in sorted(plan.changes, key=lambda c: (c.priority, c.bullet_id)):
        b = bullet_by_id.get(ch.bullet_id)
        if not b:
            continue

        if ch.action == RewriteAction.keep:
            suggestions.append(
                RewriteSuggestion(
                    bullet_id=b.id,
                    original_latex=b.latex,
                    suggested_latex=None,
                    action=RewriteAction.keep,
                    reason=ch.reason,
                    flags=[],
                    status=SuggestionStatus.pending,
                )
            )
            continue

        if ch.action == RewriteAction.remove:
            suggestions.append(
                RewriteSuggestion(
                    bullet_id=b.id,
                    original_latex=b.latex,
                    suggested_latex="",
                    action=RewriteAction.remove,
                    reason=ch.reason,
                    flags=[],
                    status=SuggestionStatus.pending,
                )
            )
            continue

        if ch.action == RewriteAction.rewrite:
            if rewrites_used >= options.max_rewrites:
                suggestions.append(
                    RewriteSuggestion(
                        bullet_id=b.id,
                        original_latex=b.latex,
                        suggested_latex=None,
                        action=RewriteAction.keep,
                        reason="Rewrite limit reached; kept original.",
                        flags=[],
                        status=SuggestionStatus.pending,
                    )
                )
                continue

            try:
                out = rewrite_bullet(
                    bullet_latex=b.latex,
                    bullet_plain=b.plain,
                    jd_keywords=jd_keywords,
                    role_focus=jd.role_focus,
                    allowed_tools_and_skills=allowed,
                    llm=llm,
                )
            except LLMError as e:
                suggestions.append(
                    RewriteSuggestion(
                        bullet_id=b.id,
                        original_latex=b.latex,
                        suggested_latex=None,
                        action=RewriteAction.keep,
                        reason="Rewrite skipped due to malformed model output; original kept.",
                        flags=[],
                        status=SuggestionStatus.rejected,
                        rejection_reason=str(e),
                    )
                )
                continue
            candidate_latex = out.suggested_latex.strip()
            candidate_plain = latex_to_plain_for_checks(candidate_latex)
            vr = verify_bullet_rewrite(
                original_latex=b.latex,
                original_plain=b.plain,
                candidate_latex=candidate_latex,
                candidate_plain=candidate_plain,
                jd_keywords=jd_keywords,
                allowed_tools_and_skills=allowed,
                cfg=cfg,
            )
            if not vr.ok:
                suggestions.append(
                    RewriteSuggestion(
                        bullet_id=b.id,
                        original_latex=b.latex,
                        suggested_latex=None,
                        action=RewriteAction.keep,
                        reason=f"Rewrite rejected by verifier: {out.rationale}",
                        flags=vr.flags,
                        status=SuggestionStatus.rejected,
                        rejection_reason="Verifier rejected rewrite; original kept.",
                    )
                )
                continue

            rewrites_used += 1
            suggestions.append(
                RewriteSuggestion(
                    bullet_id=b.id,
                    original_latex=b.latex,
                    suggested_latex=candidate_latex,
                    action=RewriteAction.rewrite,
                    reason=ch.reason,
                    flags=vr.flags,
                    status=SuggestionStatus.pending,
                )
            )

    change_report = ChangeReport(
        summary={
            "total_bullets": len(resume.bullets),
            "planned_changes": len(plan.changes),
            "rewrite_suggestions": sum(1 for s in suggestions if s.action == RewriteAction.rewrite and s.suggested_latex),
            "rejected_rewrites": sum(1 for s in suggestions if s.status == SuggestionStatus.rejected),
        },
        suggestions=suggestions,
        kept_original_bullets=[s.bullet_id for s in suggestions if s.action != RewriteAction.rewrite],
        messages=list(messages),
    )

    # No changes are applied by default. The UI/CLI can approve suggestions and call rebuild_latex.
    tailored_tex = resume.source_tex
    evaluation = None
    if options.run_evaluator:
        # Evaluate the unmodified resume by default; UI/CLI can re-evaluate after approvals.
        try:
            evaluation = evaluate_tailored_resume(jd_text=jd_text, tailored_tex=tailored_tex, llm=llm)
        except LLMError:
            messages.append("Evaluator returned an unexpected format; evaluation report was skipped.")
            evaluation = None
    # Keep messages in sync in case later stages appended warnings.
    change_report.messages = list(messages)

    return PipelineResult(
        tailored_tex=tailored_tex,
        change_report=change_report,
        evaluation_report=evaluation,
        artifacts=PipelineArtifacts(jd_analysis=jd, evidence_map=evidence, rewrite_plan=plan),
    )


def apply_user_approvals(resume_tex: str, parsed_resume: ParsedResume, change_report: ChangeReport) -> str:
    # Only approved suggestions are applied.
    return rebuild_latex(parsed_resume, change_report.suggestions)
