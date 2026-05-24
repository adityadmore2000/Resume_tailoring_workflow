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
                        company="Unclear from resume",
                        title="Unclear from resume",
                        date_range="Unclear from resume",
                        location="Unclear from resume",
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
            company = _strip_tex_commands(args[0]) if len(args) > 0 else "Unclear from resume"
            date_range = _strip_tex_commands(args[1]) if len(args) > 1 else "Unclear from resume"
            title = _strip_tex_commands(args[2]) if len(args) > 2 else "Unclear from resume"
            location = _strip_tex_commands(args[3]) if len(args) > 3 else "Unclear from resume"
            work.append(
                WorkExperienceEntry(
                    entry_id=_stable_id("work", f"{company}|{title}|{date_range}|{location}"),
                    company=company or "Unclear from resume",
                    title=title or "Unclear from resume",
                    date_range=date_range or "Unclear from resume",
                    location=location or "Unclear from resume",
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
