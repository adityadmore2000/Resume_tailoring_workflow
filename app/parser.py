from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.schemas import Bullet, ParsedResume, ResumeSection, SectionName


_SECTION_RE = re.compile(r"\\section\*?\{(?P<title>[^}]+)\}", re.MULTILINE)
_RESUME_ITEM_MACRO = r"\resumeItem{"


def _strip_latex(text: str) -> str:
    # Minimal LaTeX -> plain converter for matching/evidence.
    text = re.sub(r"%.*?$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\\textbf\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\emph\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\href\{[^}]*\}\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", "", text)
    text = re.sub(r"[{}]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_section(title: str) -> SectionName:
    t = title.strip().casefold()
    if "summary" in t:
        return SectionName.summary
    if "skill" in t:
        return SectionName.skills
    if "experience" in t or "work" in t:
        return SectionName.experience
    if "project" in t:
        return SectionName.projects
    if "education" in t:
        return SectionName.education
    return SectionName.other


def _stable_bullet_id(section: SectionName, index: int, latex: str) -> str:
    norm = re.sub(r"\s+", " ", latex.strip())
    h = hashlib.sha1(f"{section.value}|{index}|{norm}".encode("utf-8")).hexdigest()[:12]
    return f"b_{h}"


@dataclass(frozen=True)
class ParseOptions:
    max_bullets: int = 3000


def _find_balanced_brace(text: str, open_brace_index: int) -> tuple[int, int] | None:
    """
    Given an index pointing at '{', return (content_start, content_end) where content_end is
    the index of the matching '}' (exclusive for slicing end).
    """
    if open_brace_index < 0 or open_brace_index >= len(text) or text[open_brace_index] != "{":
        return None
    depth = 0
    for i in range(open_brace_index, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return (open_brace_index + 1, i)
    return None


def _extract_resume_item_bullets(
    raw: str, section_abs_start: int, section: SectionName, start_index: int
) -> list[Bullet]:
    bullets: list[Bullet] = []
    search_from = 0
    idx = start_index
    while True:
        j = raw.find(_RESUME_ITEM_MACRO, search_from)
        if j == -1:
            break
        open_brace_index = j + len(_RESUME_ITEM_MACRO) - 1  # points at '{'
        span = _find_balanced_brace(raw, open_brace_index)
        if span is None:
            search_from = j + len(_RESUME_ITEM_MACRO)
            continue
        body_start, body_end = span  # relative to raw
        body = raw[body_start:body_end]
        body_stripped = body.strip()
        body_plain = _strip_latex(body_stripped)
        bid = _stable_bullet_id(section, idx, body_stripped)
        bullets.append(
            Bullet(
                id=bid,
                section=section,
                index=idx,
                latex=body_stripped,
                plain=body_plain,
                span_start=section_abs_start + body_start,
                span_end=section_abs_start + body_end,
            )
        )
        idx += 1
        search_from = body_end + 1
    return bullets


def parse_latex_resume(source_tex: str, options: ParseOptions | None = None) -> ParsedResume:
    options = options or ParseOptions()

    sections: list[ResumeSection] = []
    bullets: list[Bullet] = []
    warnings: list[str] = []

    section_matches = list(_SECTION_RE.finditer(source_tex))
    if not section_matches:
        # Single "Other" section fallback
        section_matches = []
        warnings.append("No \\section{...} headers found. Parsed as a single raw section.")

    boundaries: list[tuple[int, int, str]] = []
    if section_matches:
        for i, m in enumerate(section_matches):
            start = m.start()
            end = section_matches[i + 1].start() if i + 1 < len(section_matches) else len(source_tex)
            boundaries.append((start, end, m.group("title")))
    else:
        boundaries.append((0, len(source_tex), "Other"))

    for start, end, title in boundaries:
        raw = source_tex[start:end]
        sec = ResumeSection(
            name=_normalize_section(title),
            title_raw=title.strip(),
            span_start=start,
            span_end=end,
            raw_text=raw,
            bullets=[],
        )

        # Bullets inside this section: capture content after \item.
        bullet_re = re.compile(
            r"(?s)\\item\s+(?P<body>.+?)(?=(?:\n\s*\\item\b)|(?:\n\s*\\end\{itemize\})|(?:\n\s*\\section\b)|\Z)"
        )
        idx = 0
        for bm in bullet_re.finditer(raw):
            if len(bullets) >= options.max_bullets:
                break
            body = bm.group("body").strip()
            body_plain = _strip_latex(body)
            body_span_start = start + bm.start("body")
            body_span_end = start + bm.end("body")
            bid = _stable_bullet_id(sec.name, idx, body)
            b = Bullet(
                id=bid,
                section=sec.name,
                index=idx,
                latex=body,
                plain=body_plain,
                span_start=body_span_start,
                span_end=body_span_end,
            )
            sec.bullets.append(b)
            bullets.append(b)
            idx += 1

        # Custom macro bullets used by many resume templates: \resumeItem{...}
        # We extract the macro *argument* and keep its span for safe surgical replacement.
        macro_bullets = _extract_resume_item_bullets(raw, start, sec.name, start_index=idx)
        if macro_bullets:
            for mb in macro_bullets:
                sec.bullets.append(mb)
                bullets.append(mb)

        sections.append(sec)

    extracted_skills, extracted_tools = extract_skills_and_tools(sections)

    if not bullets:
        warnings.append(
            "No bullets detected (no \\item or \\resumeItem{...}). The resume will be preserved unchanged."
        )

    return ParsedResume(
        source_tex=source_tex,
        sections=sections,
        bullets=bullets,
        extracted_tools=extracted_tools,
        extracted_skills=extracted_skills,
        warnings=warnings,
    )


def extract_skills_and_tools(sections: list[ResumeSection]) -> tuple[list[str], list[str]]:
    skills_text = ""
    for s in sections:
        if s.name == SectionName.skills:
            skills_text += "\n" + _strip_latex(s.raw_text)

    tokens: list[str] = []
    if skills_text.strip():
        parts = re.split(r"[,/;|]\s*|\s{2,}", skills_text)
        for p in parts:
            p = p.strip(" -\t\r\n")
            if not p:
                continue
            # Remove "Languages:"-style prefixes
            p = re.sub(r"^[A-Za-z ]{2,}:\s*", "", p).strip()
            if not p:
                continue
            tokens.append(p)

    normalized: list[str] = []
    seen: set[str] = set()
    for t in tokens:
        t = re.sub(r"\s+", " ", t).strip()
        if not t:
            continue
        key = t.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(t)

    # Heuristic split: treat everything as skills, plus a conservative tools subset
    tools = [t for t in normalized if t.casefold() in {"git", "docker", "kubernetes", "ollama"}]
    return normalized, tools
