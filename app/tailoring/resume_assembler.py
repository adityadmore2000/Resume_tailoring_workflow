from __future__ import annotations

import json
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
    # Template snapshots usually contain macro *definitions* (e.g. `\newcommand{\resumeItem}`),
    # not necessarily literal usages like `\resumeItem{`.
    return all(x in template_preamble for x in (r"\resumeSubheading", r"\resumeSubHeadingListStart", r"\resumeItem"))


def _term_match(term: str, text: str) -> bool:
    term = (term or "").strip()
    if not term:
        return False
    return bool(re.search(rf"(?i)\b{re.escape(term)}\b", text))


def _entry_relevance_score(entry_evidence_text: str, jd: JDAnalysis) -> float:
    terms = jd.required_skills + jd.important_keywords + jd.preferred_skills
    hits = sum(1 for t in terms if _term_match(t, entry_evidence_text))
    return float(hits)


def _order_experience_entries(
    *,
    work: list[WorkExperienceEntry],
    evidence_text_by_id: dict[str, str],
    jd: JDAnalysis,
) -> list[WorkExperienceEntry]:
    """
    Order experience entries by JD relevance, but NEVER drop entries.
    """
    scored: list[tuple[float, int, WorkExperienceEntry]] = []
    for idx, w in enumerate(work):
        blob = " ".join(evidence_text_by_id.get(eid, "") for eid in (w.evidence_ids or []))
        scored.append((_entry_relevance_score(blob, jd), idx, w))
    scored.sort(key=lambda x: (x[0], -x[1]), reverse=True)
    return [w for _, __, w in scored]


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
    return picked


def _render_experience_macros(
    *,
    entries: list[WorkExperienceEntry],
    evidence_latex_by_id: dict[str, str],
    bullet_ids_by_entry_id: dict[str, list[str]],
    max_bullets_per_entry: int = 5,
) -> str:
    lines: list[str] = []
    lines.append(r"\section{EXPERIENCE}")
    lines.append(r"\resumeSubHeadingListStart")
    for w in entries:
        # Preserve original hierarchy: do NOT merge display_title/subtitle.
        display_title = w.display_title or "Unclear from resume"
        subtitle = w.subtitle or "Unclear from resume"
        date_range = f"{w.start_date} - {w.end_date}".strip()
        if date_range == "-":
            date_range = "Unclear from resume"
        lines.append(r"\resumeSubheading")
        lines.append(f"{{{_sanitize_inline_latex(display_title)}}}{{{_sanitize_inline_latex(date_range)}}}")
        lines.append(f"{{{_sanitize_inline_latex(subtitle)}}}{{{_sanitize_inline_latex(w.location or '')}}}")
        lines.append(r"\resumeItemListStart")
        bullets = bullet_ids_by_entry_id.get(w.entry_id, [])
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


def _extract_section_block(tex: str, section: str, *, next_section: str | None) -> str | None:
    """
    Best-effort extraction of a full LaTeX section block from a stored master resume snapshot.
    Used only as a backward-compatible fallback when dedicated section snapshots are missing.
    """
    raw = tex or ""
    start_tok = f"\\section{{{section}}}"
    i = raw.find(start_tok)
    if i == -1:
        return None
    if next_section:
        end_tok = f"\\section{{{next_section}}}"
        j = raw.find(end_tok, i + len(start_tok))
        if j == -1:
            j = len(raw)
        block = raw[i:j].rstrip()
    else:
        j = raw.find("\\end{document}", i)
        block = raw[i:j].rstrip() if j != -1 else raw[i:].rstrip()
    return block.rstrip() + "\n"


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
    summary_path = bank_dir / "metadata" / "summary_section.tex"
    master_resume_path = bank_dir / "metadata" / "master_resume.tex"

    template_preamble = preamble_path.read_text(encoding="utf-8", errors="replace") if preamble_path.exists() else None
    template_header = header_path.read_text(encoding="utf-8", errors="replace") if header_path.exists() else None
    summary_block = summary_path.read_text(encoding="utf-8", errors="replace") if summary_path.exists() else None
    education_path = bank_dir / "metadata" / "education_section.tex"
    education_block = education_path.read_text(encoding="utf-8", errors="replace") if education_path.exists() else None
    if template_preamble is None:
        messages.append("No LaTeX template preamble found in bank; using generic LaTeX template.")
    if summary_block is None:
        if master_resume_path.exists():
            raw_master = master_resume_path.read_text(encoding="utf-8", errors="replace")
            recovered = _extract_section_block(raw_master, "SUMMARY", next_section="EXPERIENCE")
            if recovered:
                messages.append("SUMMARY snapshot missing; recovered SUMMARY from master_resume.tex stored in bank metadata.")
                summary_block = recovered
            else:
                messages.append("No SUMMARY snapshot found and recovery failed; inserting a placeholder SUMMARY section.")
                summary_block = "\\section{SUMMARY}\n\\small{Unclear from resume.}\n"
        else:
            messages.append("No SUMMARY section snapshot found in bank; inserting a placeholder SUMMARY section.")
            summary_block = "\\section{SUMMARY}\n\\small{Unclear from resume.}\n"
    if education_block is None:
        if master_resume_path.exists():
            raw_master = master_resume_path.read_text(encoding="utf-8", errors="replace")
            recovered = _extract_section_block(raw_master, "EDUCATION", next_section=None)
            if recovered:
                messages.append("EDUCATION snapshot missing; recovered EDUCATION from master_resume.tex stored in bank metadata.")
                education_block = recovered
            else:
                messages.append("No EDUCATION snapshot found and recovery failed; inserting a placeholder EDUCATION section.")
                education_block = "\\section{EDUCATION}\n\\small{Unclear from resume.}\n"
        else:
            messages.append("No EDUCATION section snapshot found in bank; inserting a placeholder EDUCATION section.")
            education_block = "\\section{EDUCATION}\n\\small{Unclear from resume.}\n"
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
    evidence_text_by_id = {eid: c.claim_text for eid, c in claim_by_id.items()}
    evidence_latex_by_id = {eid: c.source_text for eid, c in claim_by_id.items()}

    # Select most relevant experience/projects first (deterministic).
    exp_entries = _order_experience_entries(
        work=bank_index.work_experience,
        evidence_text_by_id=evidence_text_by_id,
        jd=jd,
    )
    proj_entries = _select_projects(
        projects=bank_index.projects,
        evidence_text_by_id=evidence_text_by_id,
        jd=jd,
        verified_ids=verified_ids,
        max_projects=max_projects,
    )

    # Bullet selection per entry:
    # - Prefer retrieved/verified evidence IDs.
    # - If none were retrieved for an entry, fall back to evidence-backed bullets from that entry.
    bullet_ids_by_entry_id: dict[str, list[str]] = {}
    used_evidence_ids: list[str] = []
    for w in exp_entries:
        preferred = [eid for eid in (w.evidence_ids or []) if eid in verified_ids]
        if preferred:
            chosen = preferred[:5]
        else:
            fallback = [eid for eid in (w.evidence_ids or []) if eid in claim_by_id][:2]
            chosen = fallback
            if chosen:
                messages.append(f"Experience '{w.display_title}': no retrieved evidence matched JD; using fallback source-backed bullets.")
            else:
                messages.append(f"Experience '{w.display_title}': no bullets found in bank for this entry.")
        bullet_ids_by_entry_id[w.entry_id] = chosen
        used_evidence_ids.extend(chosen)
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
    # HEADER (unchanged) -> SUMMARY -> EXPERIENCE -> PROJECTS -> SKILLS -> EDUCATION (unchanged)
    pre, _ = _ensure_document_wrapped(template_preamble or "")
    out: list[str] = [pre.rstrip(), ""]
    if template_header:
        out.append(template_header.rstrip())
        out.append("")

    out.append(summary_block.strip() + "\n")

    if has_macros:
        out.append(
            _render_experience_macros(
                entries=exp_entries,
                evidence_latex_by_id=evidence_latex_by_id,
                bullet_ids_by_entry_id=bullet_ids_by_entry_id,
            )
        )
        out.append(_render_projects_macros(projects=proj_entries, evidence_latex_by_id=evidence_latex_by_id, verified_ids=verified_ids))
    else:
        # Generic fallback layout (still enforces fixed section order).
        out.append("\\section{EXPERIENCE}\n\\begin{itemize}\n")
        for w in exp_entries:
            date_range = f"{w.start_date} - {w.end_date}".strip()
            out.append(
                f"  \\\\item \\\\textbf{{{_sanitize_inline_latex(w.display_title)}}} ({_sanitize_inline_latex(date_range)})"
                + (f" --- {_sanitize_inline_latex(w.subtitle)}" if (w.subtitle and w.subtitle != "Unclear from resume") else "")
            )
            out.append("  \\begin{itemize}")
            for eid in bullet_ids_by_entry_id.get(w.entry_id, []):
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
    out.append(education_block.strip() + "\n")

    out.append("\\end{document}\n")
    latex = "\n".join(out).strip() + "\n"

    # Markdown/Text are derived summaries; section order is enforced similarly.
    md_sections = {
        "summary": [summary_block.strip().replace("\\section{SUMMARY}", "").strip()[:400]] if summary_block else [],
        "experience": [claim_by_id[eid].claim_text for eid in used_evidence_ids if eid in claim_by_id][:20],
        "projects": [],
        "skills": skills_supported[:40],
        "education": [],
    }
    md = (
        "## SUMMARY\n" + ("\n".join(f"- {x}" for x in md_sections["summary"]) + "\n\n" if md_sections["summary"] else "\n")
        + "## EXPERIENCE\n" + "\n".join(f"- {x}" for x in md_sections["experience"]) + "\n\n"
        + "## PROJECTS\n" + "\n".join(f"- {p.name}" for p in proj_entries) + "\n\n"
        + "## SKILLS\n" + "\n".join(f"- {s}" for s in md_sections["skills"]) + "\n"
        + "## EDUCATION\n" + (education_block.strip()[:400] if education_block else "") + "\n"
    )
    txt = _render_text(
        {
            "summary": md_sections["summary"],
            "experience": md_sections["experience"],
            "projects": [p.name for p in proj_entries],
            "capabilities": md_sections["skills"],
        }
    )

    _validate_assembled_resume(
        latex=latex,
        work_entries=exp_entries,
        source_work_entry_count=len(bank_index.work_experience),
        has_macros=has_macros,
    )
    return AssembledResume(latex=latex, markdown=md, text=txt, used_evidence_ids=used_evidence_ids, messages=messages)


def load_bank_index(bank_dir: Path) -> ExperienceBankIndex:
    """
    Load bank index with backward-compatible migration for older banks.
    """
    idx_path = bank_dir / "metadata" / "experience_bank_index.json"
    raw = idx_path.read_text(encoding="utf-8", errors="replace")
    data = json.loads(raw)

    # Migrate older WorkExperienceEntry shapes:
    # Old: {company, title, date_range, location, evidence_ids}
    # New: {display_title, subtitle, start_date, end_date, ...}
    migrated: list[dict] = []
    for w in (data.get("work_experience") or []):
        if not isinstance(w, dict):
            continue
        if "display_title" not in w and ("title" in w or "date_range" in w):
            display_title = w.get("company", "") or "Unclear from resume"
            subtitle = w.get("title", "") or "Unclear from resume"
            date_range = w.get("date_range", "") or "Unclear from resume"
            location = w.get("location", "")
            migrated.append(
                {
                    "entry_id": w.get("entry_id", ""),
                    "display_title": display_title,
                    "subtitle": subtitle,
                    "start_date": date_range.split("-", 1)[0].strip() if "-" in date_range else date_range,
                    "end_date": date_range.split("-", 1)[1].strip() if "-" in date_range else "Unclear from resume",
                    "location": location,
                    "evidence_ids": w.get("evidence_ids") or [],
                }
            )
        else:
            migrated.append(w)
    data["work_experience"] = migrated

    return ExperienceBankIndex.model_validate(data)


def _validate_assembled_resume(
    *,
    latex: str,
    work_entries: list[WorkExperienceEntry],
    source_work_entry_count: int,
    has_macros: bool,
) -> None:
    required = ["SUMMARY", "EXPERIENCE", "PROJECTS", "SKILLS", "EDUCATION"]
    positions = []
    for sec in required:
        tok = f"\\section{{{sec}}}"
        i = latex.find(tok)
        if i == -1:
            raise ValueError(f"Required section missing in assembled resume: {sec}")
        positions.append((i, sec))
    if positions != sorted(positions, key=lambda x: x[0]):
        raise ValueError("Section order is not deterministic (expected HEADER → SUMMARY → EXPERIENCE → PROJECTS → SKILLS → EDUCATION).")

    if has_macros:
        exp_start = latex.find("\\section{EXPERIENCE}")
        proj_start = latex.find("\\section{PROJECTS}")
        if exp_start != -1 and proj_start != -1 and proj_start > exp_start:
            exp_block = latex[exp_start:proj_start]
            rendered = exp_block.count("\\resumeSubheading")
        else:
            rendered = latex.count("\\resumeSubheading")
        if rendered != source_work_entry_count:
            raise ValueError(f"Experience completeness violated: rendered {rendered} entries, expected {source_work_entry_count}.")

    # Title preservation: ensure each display_title and subtitle appears as separate lines.
    for w in work_entries:
        if w.display_title and w.display_title not in latex:
            raise ValueError(f"Experience title not preserved in output: {w.display_title}")
        if w.subtitle and w.subtitle not in latex:
            raise ValueError(f"Experience subtitle not preserved in output: {w.subtitle}")
