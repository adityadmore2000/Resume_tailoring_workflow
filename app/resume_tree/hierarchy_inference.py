from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from app.db.models import ResumeNode


_SECTION_CANONICAL_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"summary|profile", re.I), "summary"),
    (re.compile(r"experience|work", re.I), "experience"),
    (re.compile(r"project", re.I), "projects"),
    (re.compile(r"skill", re.I), "skills"),
    (re.compile(r"education", re.I), "education"),
    (re.compile(r"cert", re.I), "certifications"),
    (re.compile(r"publication", re.I), "publications"),
    (re.compile(r"achievement|award", re.I), "achievements"),
]


def canonical_section_label(raw: str | None) -> str:
    s = (raw or "").strip()
    if not s:
        return "other"
    for pat, label in _SECTION_CANONICAL_MAP:
        if pat.search(s):
            return label
    return "other"


def nearest_section_ancestor(
    node: ResumeNode,
    *,
    by_id: dict[uuid.UUID, ResumeNode],
) -> ResumeNode | None:
    cur = node
    seen: set[uuid.UUID] = set()
    while cur.parent_id is not None:
        pid = cur.parent_id
        if pid in seen:
            return None
        seen.add(pid)
        p = by_id.get(pid)
        if p is None:
            return None
        if p.node_type == "section":
            return p
        cur = p
    return None


def infer_section_label(
    node: ResumeNode,
    *,
    by_id: dict[uuid.UUID, ResumeNode],
) -> tuple[str, list[str]]:
    """
    Infer a node's `section_label` from its nearest section ancestor.
    Returns (label, ambiguities).
    """
    ambiguities: list[str] = []
    sec = node if node.node_type == "section" else nearest_section_ancestor(node, by_id=by_id)
    if sec is None:
        ambiguities.append("No section ancestor found; section_label defaults to 'other'.")
        return "other", ambiguities

    md = sec.metadata_ or {}
    if isinstance(md, dict):
        v = md.get("section_label")
        if isinstance(v, str) and v.strip():
            return v.strip(), ambiguities

    raw = ""
    if isinstance(sec.content, dict):
        raw = str(sec.content.get("section_name") or "")
    if not raw:
        raw = str(sec.title or "")
    label = canonical_section_label(raw)
    if label == "other":
        ambiguities.append(f"Unrecognized section heading '{raw.strip() or '∅'}'; canonicalized to 'other'.")
    return label, ambiguities


def infer_semantic_role(
    node: ResumeNode,
    *,
    by_id: dict[uuid.UUID, ResumeNode],
    children_by_parent: dict[uuid.UUID | None, list[ResumeNode]],
) -> tuple[str, list[str]]:
    """
    Infer a deterministic semantic role from hierarchy + metadata, without requiring semantic node_type values.
    Returns (role, ambiguities).
    """
    ambiguities: list[str] = []
    md = node.metadata_ or {}
    if isinstance(md, dict):
        explicit = md.get("semantic_role")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip(), ambiguities

    if node.parent_id is None:
        return "resume_root", ambiguities

    if node.node_type == "section":
        return "section", ambiguities

    section_label, sec_amb = infer_section_label(node, by_id=by_id)
    ambiguities.extend(sec_amb)

    has_children = bool(children_by_parent.get(node.id))

    if node.node_type == "item":
        if section_label == "experience" and has_children:
            return "experience_item", ambiguities
        if section_label == "projects" and has_children:
            return "project_item", ambiguities
        if section_label == "skills":
            return "skill_group", ambiguities
        if section_label == "education":
            return "education_item", ambiguities
        return f"{section_label}_item" if section_label != "other" else "item", ambiguities

    # Structural leaf/detail nodes (including legacy "bullet" etc.)
    if section_label == "skills":
        return "skill_detail", ambiguities
    if section_label != "other":
        return f"{section_label}_detail", ambiguities
    return "detail", ambiguities


def is_searchable(node: ResumeNode) -> tuple[bool, list[str]]:
    md = node.metadata_ or {}
    if not isinstance(md, dict):
        return False, ["metadata is not a dict"]
    if md.get("searchable") is not True:
        return False, ["metadata.searchable is not true"]
    src = md.get("source_text")
    if not isinstance(src, str) or not src.strip():
        return False, ["metadata.source_text is empty"]
    return True, []


@dataclass(frozen=True)
class InferredNodeView:
    node_id: uuid.UUID
    node_type: str
    section_label: str
    inferred_semantic_role: str
    searchable: bool
    ambiguities: list[str]


def infer_nodes(nodes: list[ResumeNode]) -> dict[uuid.UUID, InferredNodeView]:
    by_id: dict[uuid.UUID, ResumeNode] = {n.id: n for n in nodes}
    children_by_parent: dict[uuid.UUID | None, list[ResumeNode]] = {}
    for n in nodes:
        children_by_parent.setdefault(n.parent_id, []).append(n)

    out: dict[uuid.UUID, InferredNodeView] = {}
    for n in nodes:
        section_label, amb1 = infer_section_label(n, by_id=by_id)
        role, amb2 = infer_semantic_role(n, by_id=by_id, children_by_parent=children_by_parent)
        searchable, amb3 = is_searchable(n)
        out[n.id] = InferredNodeView(
            node_id=n.id,
            node_type=n.node_type,
            section_label=section_label,
            inferred_semantic_role=role,
            searchable=searchable,
            ambiguities=[*amb1, *amb2, *amb3],
        )
    return out
