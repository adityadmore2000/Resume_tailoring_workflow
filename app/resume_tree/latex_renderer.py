from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from app.resume_tree.hierarchy_inference import canonical_section_label
from app.resume_tree.renderable import RenderableNode, RenderableResume


def escape_latex_text(text: str) -> str:
    """
    Escape LaTeX special chars for plain-text insertion.

    Note: this is intentionally minimal and only used when we *don't* already
    have a LaTeX fragment. Existing LaTeX fragments are passed through.
    """
    s = text or ""
    # Order matters: backslash first.
    s = s.replace("\\", r"\textbackslash{}")
    s = s.replace("&", r"\&")
    s = s.replace("%", r"\%")
    s = s.replace("$", r"\$")
    s = s.replace("#", r"\#")
    s = s.replace("_", r"\_")
    s = s.replace("{", r"\{")
    s = s.replace("}", r"\}")
    s = s.replace("~", r"\textasciitilde{}")
    s = s.replace("^", r"\textasciicircum{}")
    return s


def _section_title(node: RenderableNode) -> str:
    t = (node.title or "").strip()
    if t:
        return t
    md = node.metadata or {}
    raw = ""
    if isinstance(node.content, dict):
        raw = str(node.content.get("section_name") or "")
    if not raw and isinstance(md, dict):
        raw = str(md.get("section_label") or "")
    raw = (raw or "").strip()
    return raw or "Section"


def _semantic_detail_text(node: RenderableNode) -> str:
    """
    Extract semantic text for rendering.

    This must not treat imported LaTeX fragments as canonical content.
    """
    content = node.content or {}
    if isinstance(content, dict):
        v_plain = content.get("plain")
        if isinstance(v_plain, str) and v_plain.strip():
            return v_plain.strip()
        v_text = content.get("text")
        if isinstance(v_text, str) and v_text.strip():
            return v_text.strip()
    md = node.metadata or {}
    if isinstance(md, dict):
        src = md.get("source_text")
        if isinstance(src, str) and src.strip():
            return src.strip()
    return ""


def _iter_sections(resume: RenderableResume) -> list[RenderableNode]:
    """
    Select top-level section nodes under the resume_root.
    """
    roots = resume.roots or []
    root = None
    for r in roots:
        if r.node_type == "resume_root":
            root = r
            break
    if root is None:
        return []
    secs = [c for c in (root.children or []) if c.node_type == "section"]
    secs.sort(key=lambda n: n.order_index)
    return secs


def render_resume_to_latex(
    *,
    resume: RenderableResume,
    bullet_overrides: dict[uuid.UUID, str] | None = None,
    preserve_imported_latex: bool = False,
) -> str:
    """
    Render a full standalone LaTeX document from the resume tree.

    This renderer is intentionally "system-owned":
    - No dependence on the original uploaded LaTeX template/macros
    - Works even when span_start/span_end are missing/invalid
    """
    overrides = bullet_overrides or {}

    # Minimal template: keep it compile-friendly in common environments.
    preamble = r"""\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[hidelinks]{hyperref}
\usepackage{enumitem}
\setlist[itemize]{leftmargin=*,noitemsep,topsep=0pt}
\begin{document}
"""

    lines: list[str] = [preamble]

    # Optional title header (simple).
    title = (resume.title or "").strip()
    if title:
        lines.append(r"\begin{center}")
        lines.append(r"{\LARGE " + escape_latex_text(title) + r"}")
        lines.append(r"\end{center}")
        lines.append("")

    for sec in _iter_sections(resume):
        sec_title = _section_title(sec)
        lines.append(r"\section*{" + escape_latex_text(sec_title) + "}")

        # Collect detail nodes under this section.
        details: list[RenderableNode] = []
        items = [c for c in (sec.children or []) if c.node_type in {"item", "detail"}]
        items.sort(key=lambda n: n.order_index)
        for it in items:
            if it.node_type == "detail":
                details.append(it)
                continue
            # item -> details
            kids = list(it.children or [])
            kids.sort(key=lambda n: n.order_index)
            for d in kids:
                if d.node_type == "detail":
                    details.append(d)

        # Render as bullets if we have any detail text.
        rendered: list[str] = []
        for d in details:
            # Overrides are treated as plain text (escape at render time).
            if d.node_id in overrides:
                rendered.append(escape_latex_text(str(overrides[d.node_id] or "").strip()))
                continue

            # Preserve mode: allow using the imported/provenance LaTeX fragment as-is.
            if preserve_imported_latex and isinstance(d.content, dict):
                v = d.content.get("latex")
                if isinstance(v, str) and v.strip():
                    rendered.append(v.strip())
                    continue

            # Default mode: render from semantic text only (escaped).
            txt = _semantic_detail_text(d)
            if txt:
                rendered.append(escape_latex_text(txt))
        rendered = [x for x in rendered if x.strip()]

        if rendered:
            lines.append(r"\begin{itemize}")
            for b in rendered:
                # Keep bullet content as-is (it's already LaTeX-safe or escaped above).
                lines.append(r"\item " + b)
            lines.append(r"\end{itemize}")
        else:
            lines.append(r"\vspace{0.2em}")

        lines.append("")

    lines.append(r"\end{document}")
    return "\n".join(lines).strip() + "\n"


def render_resume_diagnostics(
    *,
    resume: RenderableResume,
    bullet_overrides: dict[uuid.UUID, str] | None = None,
    preserve_imported_latex: bool = False,
) -> dict[str, object]:
    """
    Lightweight internal diagnostics for proving generation is tree-based.

    Counts:
    - rendered_detail_count: non-empty rendered bullets
    - skipped_detail_count: detail nodes considered but rendered empty
    - skipped_reasons: bucketed reasons (currently only "empty_detail")
    """
    overrides = bullet_overrides or {}

    details: list[RenderableNode] = []
    for sec in _iter_sections(resume):
        items = [c for c in (sec.children or []) if c.node_type in {"item", "detail"}]
        items.sort(key=lambda n: n.order_index)
        for it in items:
            if it.node_type == "detail":
                details.append(it)
                continue
            kids = list(it.children or [])
            kids.sort(key=lambda n: n.order_index)
            for d in kids:
                if d.node_type == "detail":
                    details.append(d)

    rendered = 0
    skipped = 0
    skipped_reasons: dict[str, int] = {}
    for d in details:
        if d.node_id in overrides and str(overrides[d.node_id] or "").strip():
            rendered += 1
            continue
        if preserve_imported_latex and isinstance(d.content, dict):
            v = d.content.get("latex")
            if isinstance(v, str) and v.strip():
                rendered += 1
                continue
        txt = _semantic_detail_text(d)
        if txt.strip():
            rendered += 1
        else:
            skipped += 1
            skipped_reasons["empty_detail"] = skipped_reasons.get("empty_detail", 0) + 1

    return {
        "detail_node_count": len(details),
        "rendered_detail_count": rendered,
        "skipped_detail_count": skipped,
        "skipped_reasons": skipped_reasons,
    }
