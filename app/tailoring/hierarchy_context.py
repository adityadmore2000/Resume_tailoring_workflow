from __future__ import annotations

import uuid
from collections import defaultdict

from app.db.models import ResumeNode
from app.resume_tree.hierarchy_inference import infer_nodes, is_searchable, nearest_section_ancestor


def build_tailoring_context(
    *,
    nodes: list[ResumeNode],
    matched_node_ids: list[uuid.UUID],
) -> tuple[dict[str, object], dict[str, object]]:
    """
    Build a deterministic context bundle using the hierarchy:
      Section -> Item -> Detail

    Returns:
      (context, debug)
    """
    by_id: dict[uuid.UUID, ResumeNode] = {n.id: n for n in nodes}
    children_by_parent: dict[uuid.UUID | None, list[ResumeNode]] = defaultdict(list)
    for n in nodes:
        children_by_parent[n.parent_id].append(n)
    for siblings in children_by_parent.values():
        siblings.sort(key=lambda n: (n.order_index, n.created_at))

    inferred = infer_nodes(nodes)

    included: set[uuid.UUID] = set()
    include_reasons: dict[uuid.UUID, list[str]] = defaultdict(list)
    exclude_reasons: dict[uuid.UUID, list[str]] = defaultdict(list)

    def _include(nid: uuid.UUID, reason: str) -> None:
        included.add(nid)
        include_reasons[nid].append(reason)

    # 1) Resolve matched nodes to "detail evidence" nodes.
    evidence_details: set[uuid.UUID] = set()
    for mid in matched_node_ids:
        n = by_id.get(mid)
        if n is None:
            continue
        if n.node_type == "detail":
            evidence_details.add(n.id)
            continue
        if n.node_type == "item":
            for c in children_by_parent.get(n.id, []):
                ok, _ = is_searchable(c)
                if ok:
                    evidence_details.add(c.id)
            continue
        ok, _ = is_searchable(n)
        if ok:
            evidence_details.add(n.id)

    # 2) Include evidence details + ancestors to section + root.
    for did in sorted(evidence_details):
        d = by_id.get(did)
        if d is None:
            continue
        ok, reasons = is_searchable(d)
        if not ok:
            exclude_reasons[did].extend([f"matched_but_not_searchable: {r}" for r in reasons])
            continue
        _include(did, "matched_detail")

        # Parent item
        if d.parent_id is not None and d.parent_id in by_id:
            _include(d.parent_id, "parent_item_of_matched_detail")

        # Nearest section
        sec = nearest_section_ancestor(d, by_id=by_id)
        if sec is not None:
            _include(sec.id, "section_of_matched_detail")

        # Root
        cur = d
        seen: set[uuid.UUID] = set()
        while cur.parent_id is not None and cur.parent_id not in seen:
            seen.add(cur.parent_id)
            p = by_id.get(cur.parent_id)
            if p is None:
                break
            if p.parent_id is None:
                _include(p.id, "resume_root_ancestor")
                break
            cur = p

    # 3) Expand: if an item is included, include all its searchable detail children for coherence.
    for nid in list(included):
        n = by_id.get(nid)
        if n is None or n.node_type != "item":
            continue
        for c in children_by_parent.get(n.id, []):
            ok, _ = is_searchable(c)
            if ok:
                if c.id not in included:
                    _include(c.id, "same_item_context")

    # 4) Build structured context (sections -> items -> details).
    sections_out: list[dict[str, object]] = []
    for n in children_by_parent.get(None, []):
        # Root(s)
        if n.id not in included:
            continue
        for sec in children_by_parent.get(n.id, []):
            if sec.id not in included or sec.node_type != "section":
                continue
            sec_view = inferred.get(sec.id)
            sec_label = sec_view.section_label if sec_view is not None else "other"
            sec_obj: dict[str, object] = {
                "node_id": str(sec.id),
                "section_label": sec_label,
                "title": sec.title or "",
                "items": [],
            }

            items_out: list[dict[str, object]] = []
            for item in children_by_parent.get(sec.id, []):
                if item.id not in included or item.node_type != "item":
                    continue
                item_view = inferred.get(item.id)
                item_role = item_view.inferred_semantic_role if item_view is not None else "item"
                item_obj: dict[str, object] = {
                    "node_id": str(item.id),
                    "inferred_semantic_role": item_role,
                    "title": item.title or "",
                    "metadata": item.metadata_ or {},
                    "details": [],
                }
                details_out: list[dict[str, object]] = []
                for d in children_by_parent.get(item.id, []):
                    if d.id not in included:
                        continue
                    d_view = inferred.get(d.id)
                    md = d.metadata_ or {}
                    details_out.append(
                        {
                            "node_id": str(d.id),
                            "node_type": d.node_type,
                            "inferred_semantic_role": d_view.inferred_semantic_role if d_view is not None else "",
                            "searchable": bool((md or {}).get("searchable") is True) if isinstance(md, dict) else False,
                            "source_text": (md.get("source_text") if isinstance(md, dict) else "") or "",
                            "evidence_ids": md.get("evidence_ids", []) if isinstance(md, dict) else [],
                            "tools": md.get("tools", []) if isinstance(md, dict) else [],
                            "skills": md.get("skills", []) if isinstance(md, dict) else [],
                            "metadata": md,
                        }
                    )
                item_obj["details"] = details_out
                if details_out:
                    items_out.append(item_obj)
            sec_obj["items"] = items_out
            if items_out:
                sections_out.append(sec_obj)

    # 5) Debug per node.
    nodes_debug: list[dict[str, object]] = []
    for n in nodes:
        view = inferred.get(n.id)
        if n.id not in included and n.id not in exclude_reasons:
            exclude_reasons[n.id].append("not_reachable_from_matched_details")
        nodes_debug.append(
            {
                "node_id": str(n.id),
                "parent_id": str(n.parent_id) if n.parent_id is not None else None,
                "node_type": n.node_type,
                "section_label": view.section_label if view is not None else "other",
                "inferred_semantic_role": view.inferred_semantic_role if view is not None else "",
                "searchable": bool(view.searchable) if view is not None else False,
                "included_in_context": n.id in included,
                "include_reasons": include_reasons.get(n.id, []),
                "exclude_reasons": exclude_reasons.get(n.id, []),
                "ambiguities": view.ambiguities if view is not None else [],
            }
        )

    return (
        {"sections": sections_out},
        {
            "matched_node_ids": [str(x) for x in matched_node_ids],
            "evidence_detail_node_ids": [str(x) for x in sorted(evidence_details)],
            "included_node_ids": [str(x) for x in sorted(included)],
            "nodes": nodes_debug,
        },
    )
