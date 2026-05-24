from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.bank_generator.schemas import ExperienceBankIndex, ProjectEntry, WorkExperienceEntry
from app.schemas import JDAnalysis


@dataclass(frozen=True)
class AssembledResume:
    latex: str
    markdown: str
    text: str
    used_evidence_ids: list[str]
    messages: list[str]


def _sanitize_inline_latex(s: str) -> str:
    # Preserve inline LaTeX, but strip structural tokens that could break layout.
    s = (s or "").strip()
    for tok in (r"\section", r"\subsection", r"\begin{", r"\end{", r"\input", r"\include"):
        s = s.replace(tok, "")
    return s.strip()


def _has_resume_macros(template_preamble: str | None) -> bool:
    if not template_preamble:
        return False
    return all(x in template_preamble for x in (r"\resumeSubheading", r"\resumeSubHeadingListStart", r"\resumeItem{"))


def _term_match(term: str, text: str) -> bool:
    term = (term or "").strip()
    if not term:
        return False
    return bool(re.search(rf"(?i)\b{re.escape(term)}\b", text))


def _entry_relevance_score(entry_evidence_text: str, jd: JDAnalysis) -> float:
    terms = jd.required_skills + jd.important_keywords + jd.preferred_skills
    hits = sum(1 for t in terms if _term_match(t, entry_evidence_text))
    return float(hits)


def _select_experience_entries(
    *,
    work: list[WorkExperienceEntry],
    evidence_text_by_id: dict[str, str],
    jd: JDAnalysis,
    verified_ids: set[str],
    max_entries: int = 4,
) -> list[WorkExperienceEntry]:
    scored: list[tuple[float, WorkExperienceEntry]] = []
    for w in work:
        ids = [eid for eid in w.evidence_ids if eid in verified_ids]
        blob = " ".join(evidence_text_by_id.get(eid, "") for eid in ids)
        scored.append((_entry_relevance_score(blob, jd), w))
    scored.sort(key=lambda x: (x[0], x[1].company), reverse=True)
    picked = [w for s, w in scored if s > 0][:max_entries]
    # If nothing matches, keep the first entries but still only include verified bullets.
    if not picked:
        picked = work[:max_entries]
    return picked


def _select_projects(
    *,
    projects: list[ProjectEntry],
    evidence_text_by_id: dict[str, str],
    jd: JDAnalysis,
    verified_ids: set[str],
    max_projects: int = 4,
) -> list[ProjectEntry]:
    scored: list[tuple[float, ProjectEntry]] = []
    for p in projects:
        ids = [eid for eid in p.evidence_ids if eid in verified_ids]
        blob = " ".join(evidence_text_by_id.get(eid, "") for eid in ids)
        scored.append((_entry_relevance_score(blob, jd), p))
    scored.sort(key=lambda x: (x[0], x[1].name), reverse=True)
    picked = [p for s, p in scored if s > 0][:max_projects]
    if not picked:
        picked = projects[:max_projects]
    return picked


def _render_experience_macros(
    *,
    entries: list[WorkExperienceEntry],
    evidence_latex_by_id: dict[str, str],
    verified_ids: set[str],
    max_bullets_per_entry: int = 5,
) -> str:
    lines: list[str] = []
    lines.append(r"\section{EXPERIENCE}")
    lines.append(r"\resumeSubHeadingListStart")
    for w in entries:
        # Company-wise grouping: try to split "Role | Company" patterns.
        raw = w.company or "Unclear from resume"
        role_line = w.title or ""
        company_line = raw
        if "$|$" in raw:
            parts = [p.strip() for p in raw.split("$|$") if p.strip()]
            if len(parts) >= 2:
                role_line = role_line or parts[0]
                company_line = parts[-1]
        elif "|" in raw:
            parts = [p.strip() for p in raw.split("|") if p.strip()]
            if len(parts) >= 2:
                role_line = role_line or parts[0]
                company_line = parts[-1]
        lines.append(r"\resumeSubheading")
        lines.append(f"{{{_sanitize_inline_latex(company_line)}}}{{{_sanitize_inline_latex(w.date_range)}}}")
        lines.append(f"{{{_sanitize_inline_latex(role_line)}}}{{{_sanitize_inline_latex(w.location)}}}")
        lines.append(r"\resumeItemListStart")
        bullets = [eid for eid in w.evidence_ids if eid in verified_ids]
        for eid in bullets[:max_bullets_per_entry]:
            body = _sanitize_inline_latex(evidence_latex_by_id.get(eid, ""))
            if not body:
                continue
            lines.append(rf"\resumeItem{{{body}}}")
        lines.append(r"\resumeItemListEnd")
    lines.append(r"\resumeSubHeadingListEnd")
    return "\n".join(lines).strip() + "\n"


def _render_projects_macros(
    *,
    projects: list[ProjectEntry],
    evidence_latex_by_id: dict[str, str],
    verified_ids: set[str],
    max_bullets_per_project: int = 4,
) -> str:
    lines: list[str] = []
    lines.append(r"\section{PROJECTS}")
    lines.append(r"\resumeSubHeadingListStart")
    for p in projects:
        left = rf"\textbf{{{_sanitize_inline_latex(p.name)}}}"
        right = ""
        lines.append(r"\resumeProjectHeading")
        lines.append(f"{{{left}}}{{{right}}}")
        lines.append(r"\resumeItemListStart")
        bullets = [eid for eid in p.evidence_ids if eid in verified_ids]
        for eid in bullets[:max_bullets_per_project]:
            body = _sanitize_inline_latex(evidence_latex_by_id.get(eid, ""))
            if not body:
                continue
            lines.append(rf"\resumeItem{{{body}}}")
        lines.append(r"\resumeItemListEnd")
    lines.append(r"\resumeSubHeadingListEnd")
    return "\n".join(lines).strip() + "\n"


def _render_skills_block(*, skills: list[str]) -> str:
    skills = [s for s in skills if s and s.strip()]
    joined = ", ".join(skills[:40])
    return (
        "\\section{SKILLS}\n"
        "\\begin{itemize}[leftmargin=0in, label={}]\n"
        "\\small{\\item{\n"
        f"\\textbf{{Relevant:}} {{{_sanitize_inline_latex(joined)}}} \\\\\n"
        "}}\n"
        "\\end{itemize}\n"
    )


def _ensure_document_wrapped(preamble: str) -> tuple[str, str]:
    """
    Return (preamble_with_begin_doc, trailer_end_doc).
    """
    pre = preamble or ""
    if "\\begin{document}" in pre:
        return pre, ""
    if "\\documentclass" not in pre:
        pre = (
            "\\documentclass[11pt]{article}\n"
            "\\usepackage[margin=1in]{geometry}\n"
            "\\usepackage[hidelinks]{hyperref}\n"
            + pre
        )
    pre = pre.rstrip() + "\n\\begin{document}\n"
    return pre, ""


def _render_markdown(sections: dict[str, list[str]]) -> str:
    parts: list[str] = []
    for k, title in [("summary", "Summary"), ("experience", "Experience Highlights"), ("projects", "Project Highlights"), ("capabilities", "Capabilities")]:
        bullets = sections.get(k, [])
        if not bullets:
            continue
        parts.append(f"## {title}")
        parts.extend([f"- {b}" for b in bullets])
        parts.append("")
    return "\n".join(parts).strip() + "\n"


def _render_text(sections: dict[str, list[str]]) -> str:
    lines: list[str] = []
    for k, title in [("summary", "SUMMARY"), ("experience", "EXPERIENCE"), ("projects", "PROJECTS"), ("capabilities", "CAPABILITIES")]:
        bullets = sections.get(k, [])
        if not bullets:
            continue
        lines.append(title)
        for b in bullets:
            lines.append(f"- {b}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def assemble_from_bank(
    *,
    bank_dir: Path,
    bank_index: ExperienceBankIndex,
    verified_evidence: list[object],
    jd: JDAnalysis,
    max_experience_entries: int = 4,
    max_projects: int = 4,
) -> AssembledResume:
    """
    Assemble a tailored resume using ONLY verified evidence from the selected bank.
    No uploaded resume input is required.
    """
    messages: list[str] = []
    preamble_path = bank_dir / "metadata" / "template_preamble.tex"
    header_path = bank_dir / "metadata" / "template_body_header.tex"

    template_preamble = preamble_path.read_text(encoding="utf-8", errors="replace") if preamble_path.exists() else None
    template_header = header_path.read_text(encoding="utf-8", errors="replace") if header_path.exists() else None
    education_path = bank_dir / "metadata" / "education_section.tex"
    education_block = education_path.read_text(encoding="utf-8", errors="replace") if education_path.exists() else None
    if template_preamble is None:
        messages.append("No LaTeX template preamble found in bank; using generic LaTeX template.")
    if education_block is None:
        messages.append("No EDUCATION section snapshot found in bank; education will be omitted.")
    else:
        if "\\end{document}" in education_block:
            # Older banks may include trailing \end{document} in the snapshot; strip it.
            education_block = education_block.split("\\end{document}", 1)[0].rstrip() + "\n"

    has_macros = _has_resume_macros(template_preamble)
    if not has_macros:
        messages.append("Resume macros not detected in template; using a generic LaTeX layout for sections.")

    # Verified evidence IDs (hard constraint: no evidence_id => no bullet).
    verified_ids: set[str] = set()
    for e in verified_evidence:
        eid = getattr(e, "evidence_id", None)
        if isinstance(eid, str) and eid:
            verified_ids.add(eid)

    claim_by_id = {c.evidence_id: c for c in bank_index.evidence_claims}
    evidence_text_by_id = {eid: claim_by_id[eid].claim_text for eid in verified_ids if eid in claim_by_id}
    evidence_latex_by_id = {eid: claim_by_id[eid].source_text for eid in verified_ids if eid in claim_by_id}

    # Select most relevant experience/projects first (deterministic).
    exp_entries = _select_experience_entries(
        work=bank_index.work_experience,
        evidence_text_by_id=evidence_text_by_id,
        jd=jd,
        verified_ids=verified_ids,
        max_entries=max_experience_entries,
    )
    proj_entries = _select_projects(
        projects=bank_index.projects,
        evidence_text_by_id=evidence_text_by_id,
        jd=jd,
        verified_ids=verified_ids,
        max_projects=max_projects,
    )

    used_evidence_ids: list[str] = []
    for w in exp_entries:
        used_evidence_ids.extend([eid for eid in w.evidence_ids if eid in verified_ids])
    for p in proj_entries:
        used_evidence_ids.extend([eid for eid in p.evidence_ids if eid in verified_ids])
    used_evidence_ids = list(dict.fromkeys(used_evidence_ids))

    # Skills from used evidence: keep only capabilities explicitly supported by evidence IDs.
    skills_supported: list[str] = []
    for cap in bank_index.capabilities:
        if any(eid in used_evidence_ids for eid in cap.evidence_ids):
            skills_supported.append(cap.name)
    # Prioritize JD relevance
    jd_terms = {t.casefold() for t in (jd.required_skills + jd.important_keywords + jd.preferred_skills)}
    skills_supported.sort(key=lambda s: (s.casefold() in jd_terms, s.casefold()), reverse=True)

    # Build LaTeX with deterministic section order:
    # HEADER (unchanged) -> EXPERIENCE -> PROJECTS -> SKILLS -> EDUCATION (unchanged)
    pre, _ = _ensure_document_wrapped(template_preamble or "")
    out: list[str] = [pre.rstrip(), ""]
    if template_header:
        out.append(template_header.rstrip())
        out.append("")

    if has_macros:
        out.append(_render_experience_macros(entries=exp_entries, evidence_latex_by_id=evidence_latex_by_id, verified_ids=verified_ids))
        out.append(_render_projects_macros(projects=proj_entries, evidence_latex_by_id=evidence_latex_by_id, verified_ids=verified_ids))
    else:
        # Generic fallback layout (still enforces fixed section order).
        out.append("\\section{EXPERIENCE}\n\\begin{itemize}\n")
        for w in exp_entries:
            raw = w.company or ""
            company_line = raw
            if "$|$" in raw:
                parts = [p.strip() for p in raw.split("$|$") if p.strip()]
                if parts:
                    company_line = parts[-1]
            elif "|" in raw:
                parts = [p.strip() for p in raw.split("|") if p.strip()]
                if parts:
                    company_line = parts[-1]
            out.append(f"  \\item \\textbf{{{_sanitize_inline_latex(company_line)}}} ({_sanitize_inline_latex(w.date_range)})")
            out.append("  \\begin{itemize}")
            for eid in [x for x in w.evidence_ids if x in verified_ids][:5]:
                out.append(f"    \\item {_sanitize_inline_latex(evidence_latex_by_id.get(eid, ''))}")
            out.append("  \\end{itemize}")
        out.append("\\end{itemize}\n")

        out.append("\\section{PROJECTS}\n\\begin{itemize}\n")
        for p in proj_entries:
            out.append(f"  \\item \\textbf{{{_sanitize_inline_latex(p.name)}}}")
            out.append("  \\begin{itemize}")
            for eid in [x for x in p.evidence_ids if x in verified_ids][:4]:
                out.append(f"    \\item {_sanitize_inline_latex(evidence_latex_by_id.get(eid, ''))}")
            out.append("  \\end{itemize}")
        out.append("\\end{itemize}\n")

    out.append(_render_skills_block(skills=skills_supported))
    if education_block:
        out.append(education_block.strip() + "\n")

    out.append("\\end{document}\n")
    latex = "\n".join(out).strip() + "\n"

    # Markdown/Text are derived summaries; section order is enforced similarly.
    md_sections = {
        "experience": [claim_by_id[eid].claim_text for eid in used_evidence_ids if eid in claim_by_id][:20],
        "projects": [],
        "skills": skills_supported[:40],
        "education": [],
    }
    md = (
        "## EXPERIENCE\n" + "\n".join(f"- {x}" for x in md_sections["experience"]) + "\n\n"
        + "## PROJECTS\n" + "\n".join(f"- {p.name}" for p in proj_entries) + "\n\n"
        + "## SKILLS\n" + "\n".join(f"- {s}" for s in md_sections["skills"]) + "\n"
    )
    txt = _render_text({"experience": md_sections["experience"], "projects": [p.name for p in proj_entries], "capabilities": md_sections["skills"], "summary": []})
    return AssembledResume(latex=latex, markdown=md, text=txt, used_evidence_ids=used_evidence_ids, messages=messages)


def load_bank_index(bank_dir: Path) -> ExperienceBankIndex:
    idx_path = bank_dir / "metadata" / "experience_bank_index.json"
    data = idx_path.read_text(encoding="utf-8", errors="replace")
    return ExperienceBankIndex.model_validate_json(data)
