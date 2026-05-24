from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.bank_generator.schemas import (
    AtomicEvidenceClaim,
    ExperienceBankIndex,
    MetricEntry,
    ProjectEntry,
    WorkExperienceEntry,
)
from app.schemas import ParsedResume, SectionName


_NUM_RE = re.compile(r"(?<!\\)\b\d+(?:\.\d+)?%?\b")
_DATE_SPLIT_RE = re.compile(r"\s*(?:--|–|—|-|to)\s*", flags=re.IGNORECASE)


def _stable_id(prefix: str, text: str) -> str:
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{h}"


def _strip_tex_commands(s: str) -> str:
    s = re.sub(r"%.*?$", "", s, flags=re.MULTILINE)
    s = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", "", s)
    s = re.sub(r"[{}]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _parse_date_range(raw: str) -> tuple[str, str]:
    raw = (raw or "").strip()
    if not raw:
        return "Unclear from resume", "Unclear from resume"
    parts = [p.strip() for p in _DATE_SPLIT_RE.split(raw) if p.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    # Keep what we have; don't guess.
    return raw, "Unclear from resume"


def _split_display_title(display_title_latex: str) -> tuple[str, str, str]:
    """
    Best-effort parse of "Role | Company" style titles.
    Returns (role_title, employment_type_or_label, company).
    Never invents data; returns "Unclear from resume" when uncertain.
    """
    plain = _strip_tex_commands(display_title_latex)
    # Normalize common LaTeX resume separator "$|$" into a split token.
    plain = plain.replace("$|$", "|")
    parts = [p.strip() for p in plain.split("|") if p.strip()]
    if len(parts) < 2:
        return "Unclear from resume", "", plain or "Unclear from resume"

    role = parts[0]
    right = parts[-1]
    right_cf = right.casefold()
    # Heuristic: treat these as labels rather than companies.
    label_tokens = {"freelancer", "self-employed", "independent", "contract", "contractor"}
    if right_cf in label_tokens:
        return role or "Unclear from resume", right, ""
    return role or "Unclear from resume", "", right or "Unclear from resume"


def extract_atomic_evidence(parsed: ParsedResume, *, bank_folder_name: str) -> tuple[list[AtomicEvidenceClaim], list[MetricEntry]]:
    claims: list[AtomicEvidenceClaim] = []
    metrics: list[MetricEntry] = []
    for b in parsed.bullets:
        evidence_id = _stable_id("ev", f"{b.section.value}|{b.id}|{b.plain}")
        claim = AtomicEvidenceClaim(
            evidence_id=evidence_id,
            claim_text=b.plain,
            source_section=b.section.value,
            source_text=b.latex,
            source_span_start=b.span_start,
            source_span_end=b.span_end,
            tools=[],
            metrics=[],
            notes="",
        )
        # Metrics must be explicitly present.
        nums = _NUM_RE.findall(b.plain)
        if nums:
            claim.metrics = nums
            for n in nums[:6]:
                metrics.append(MetricEntry(metric_id=_stable_id("m", f"{evidence_id}|{n}"), metric_text=n, evidence_id=evidence_id))
        claims.append(claim)
    return claims, metrics


def _find_macro_calls(raw: str, macro: str) -> list[tuple[int, int, list[str]]]:
    """
    Find macro calls like \\resumeSubheading{a}{b}{c}{d}.
    Returns list of (start_index, end_index, args).
    """
    out: list[tuple[int, int, list[str]]] = []
    i = 0
    token = "\\" + macro
    while True:
        j = raw.find(token, i)
        if j == -1:
            break
        k = j + len(token)
        args: list[str] = []
        end = k
        for _ in range(6):  # safety cap
            while end < len(raw) and raw[end].isspace():
                end += 1
            if end >= len(raw) or raw[end] != "{":
                break
            # balanced brace extract
            depth = 0
            start_arg = end + 1
            p = end
            while p < len(raw):
                if raw[p] == "{":
                    depth += 1
                elif raw[p] == "}":
                    depth -= 1
                    if depth == 0:
                        args.append(raw[start_arg:p])
                        end = p + 1
                        break
                p += 1
            else:
                break
            if macro == "resumeSubheading" and len(args) >= 4:
                break
            if macro == "resumeProjectHeading" and len(args) >= 2:
                break
        out.append((j, end, args))
        i = end
    return out


def extract_work_and_projects(parsed: ParsedResume, evidence_claims: list[AtomicEvidenceClaim]) -> tuple[list[WorkExperienceEntry], list[ProjectEntry]]:
    evidence_by_span = sorted(evidence_claims, key=lambda e: (e.source_span_start or 0))

    def evidence_in_range(start: int, end: int) -> list[str]:
        ids: list[str] = []
        for e in evidence_by_span:
            s = e.source_span_start or -1
            if s < start:
                continue
            if s >= end:
                break
            ids.append(e.evidence_id)
        return ids

    work: list[WorkExperienceEntry] = []
    projects: list[ProjectEntry] = []

    # EXPERIENCE: group bullets by resumeSubheading blocks if present.
    exp_sections = [s for s in parsed.sections if s.name == SectionName.experience]
    for sec in exp_sections:
        calls = _find_macro_calls(sec.raw_text, "resumeSubheading")
        if not calls:
            # Fallback: one entry for the whole section.
            all_ids = [e.evidence_id for e in evidence_claims if e.source_section.casefold() == "experience"]
            if all_ids:
                work.append(
                    WorkExperienceEntry(
                        entry_id=_stable_id("work", "experience_fallback"),
                        role_title="Unclear from resume",
                        employment_type_or_label="",
                        company="Unclear from resume",
                        display_title="Unclear from resume",
                        subtitle="Unclear from resume",
                        start_date="Unclear from resume",
                        end_date="Unclear from resume",
                        location="Unclear from resume",
                        source_text=sec.raw_text,
                        evidence_ids=all_ids,
                    )
                )
            break
        # Determine ranges per subheading.
        for idx, (start_rel, end_rel, args) in enumerate(calls):
            next_start_rel = calls[idx + 1][0] if idx + 1 < len(calls) else len(sec.raw_text)
            abs_start = sec.span_start + end_rel
            abs_end = sec.span_start + next_start_rel
            ev_ids = evidence_in_range(abs_start, abs_end)
            display_title = (args[0].strip() if len(args) > 0 else "") or "Unclear from resume"
            date_range = (args[1].strip() if len(args) > 1 else "") or "Unclear from resume"
            subtitle = (args[2].strip() if len(args) > 2 else "") or "Unclear from resume"
            # Preserve empty location if the resume explicitly left it blank.
            location = (args[3].strip() if len(args) > 3 else "")
            start_date, end_date = _parse_date_range(_strip_tex_commands(date_range))
            role_title, employment_type_or_label, company = _split_display_title(display_title)
            source_text = sec.raw_text[start_rel:end_rel].strip()
            work.append(
                WorkExperienceEntry(
                    entry_id=_stable_id("work", f"{display_title}|{subtitle}|{date_range}|{location}"),
                    role_title=role_title,
                    employment_type_or_label=employment_type_or_label,
                    company=company,
                    display_title=display_title,
                    subtitle=subtitle,
                    start_date=start_date,
                    end_date=end_date,
                    location=location,
                    source_text=source_text,
                    evidence_ids=ev_ids,
                )
            )

    # PROJECTS: group bullets by resumeProjectHeading blocks if present.
    proj_sections = [s for s in parsed.sections if s.name == SectionName.projects]
    for sec in proj_sections:
        calls = _find_macro_calls(sec.raw_text, "resumeProjectHeading")
        if not calls:
            break
        for idx, (start_rel, end_rel, args) in enumerate(calls):
            next_start_rel = calls[idx + 1][0] if idx + 1 < len(calls) else len(sec.raw_text)
            abs_start = sec.span_start + end_rel
            abs_end = sec.span_start + next_start_rel
            ev_ids = evidence_in_range(abs_start, abs_end)
            name = _strip_tex_commands(args[0]) if len(args) > 0 else "Unclear from resume"
            desc = _strip_tex_commands(args[1]) if len(args) > 1 else ""
            projects.append(
                ProjectEntry(
                    project_id=_stable_id("proj", f"{name}|{desc}"),
                    name=name or "Unclear from resume",
                    description=desc,
                    evidence_ids=ev_ids,
                    tools=[],
                )
            )

    return work, projects


def build_experience_bank_index(
    parsed: ParsedResume, *, bank_folder_name: str, source_format: str = "latex"
) -> ExperienceBankIndex:
    evidence_claims, metrics = extract_atomic_evidence(parsed, bank_folder_name=bank_folder_name)
    work, projects = extract_work_and_projects(parsed, evidence_claims)
    return ExperienceBankIndex(
        bank_folder_name=bank_folder_name,
        source_format="text" if source_format == "text" else "latex",
        sections=[],
        evidence_claims=evidence_claims,
        work_experience=work,
        projects=projects,
        capabilities=[],
        deployments=[],
        metrics=metrics,
        reusable_bullets=[],
    )
