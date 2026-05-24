from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.bank_generator.schemas import ExperienceBankIndex
from app.tailoring.evidence_verifier import VerifiedEvidence


@dataclass(frozen=True)
class AssembledResume:
    latex: str
    markdown: str
    text: str
    used_evidence_ids: list[str]
    messages: list[str]


def _sanitize_latex_bullet(s: str) -> str:
    # Keep LaTeX from source_text mostly intact, but ensure it doesn't inject structure.
    s = s.strip()
    for tok in (r"\section", r"\subsection", r"\begin{", r"\end{", r"\input", r"\include"):
        s = s.replace(tok, "")
    return s.strip()


def _render_latex(
    *,
    template_preamble: str | None,
    template_body_header: str | None,
    sections: dict[str, list[str]],
) -> str:
    # Generic fallback preamble if template is missing.
    pre = template_preamble or (
        "\\documentclass[11pt]{article}\n"
        "\\usepackage[margin=1in]{geometry}\n"
        "\\usepackage[hidelinks]{hyperref}\n"
        "\\begin{document}\n"
    )
    if "\\begin{document}" not in pre:
        pre = pre.rstrip() + "\n\\begin{document}\n"
    out = [pre.rstrip(), ""]

    if template_body_header:
        out.append(template_body_header.strip())
        out.append("")

    def sec(title: str, bullets: list[str]) -> None:
        if not bullets:
            return
        out.append(f"\\section{{{title}}}")
        out.append("\\begin{itemize}")
        for b in bullets:
            out.append(f"  \\item {b}")
        out.append("\\end{itemize}")
        out.append("")

    sec("Summary", sections.get("summary", []))
    sec("Experience Highlights", sections.get("experience", []))
    sec("Project Highlights", sections.get("projects", []))
    sec("Capabilities", sections.get("capabilities", []))

    out.append("\\end{document}")
    return "\n".join(out).strip() + "\n"


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
    verified_evidence: list[VerifiedEvidence],
    max_bullets: int = 18,
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
    if template_preamble is None:
        messages.append("No LaTeX template preamble found in bank; using generic LaTeX template.")

    # Pick bullets from verified evidence, prefer supported > partial.
    supported = [e for e in verified_evidence if e.support == "supported"]
    partial = [e for e in verified_evidence if e.support != "supported"]
    picked = (supported + partial)[:max_bullets]

    sections: dict[str, list[str]] = {"summary": [], "experience": [], "projects": [], "capabilities": []}
    used_ids: list[str] = []

    # Heuristic section routing based on source_section hint stored in evidence claim.
    claim_by_id = {c.evidence_id: c for c in bank_index.evidence_claims}
    for e in picked:
        c = claim_by_id.get(e.evidence_id)
        if not c:
            continue
        used_ids.append(e.evidence_id)
        bullet = _sanitize_latex_bullet(c.source_text)
        sec = (c.source_section or "").casefold()
        if "project" in sec:
            sections["projects"].append(bullet)
        elif "experience" in sec or "work" in sec:
            sections["experience"].append(bullet)
        elif "summary" in sec:
            # Summaries from evidence are usually long; keep as a single sentence.
            sections["summary"].append(re.sub(r"\s+", " ", c.claim_text).strip()[:220])
        else:
            sections["capabilities"].append(bullet)

    latex = _render_latex(template_preamble=template_preamble, template_body_header=template_header, sections=sections)
    md = _render_markdown(sections)
    txt = _render_text(sections)
    return AssembledResume(latex=latex, markdown=md, text=txt, used_evidence_ids=used_ids, messages=messages)


def load_bank_index(bank_dir: Path) -> ExperienceBankIndex:
    idx_path = bank_dir / "metadata" / "experience_bank_index.json"
    data = idx_path.read_text(encoding="utf-8", errors="replace")
    return ExperienceBankIndex.model_validate_json(data)
