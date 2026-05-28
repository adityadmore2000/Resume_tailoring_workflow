from __future__ import annotations

from collections import defaultdict

from app.db.models import ResumeNode


def build_tree(nodes: list[ResumeNode]) -> list[dict]:
    by_parent: dict[object | None, list[ResumeNode]] = defaultdict(list)
    for node in nodes:
        by_parent[node.parent_id].append(node)

    for siblings in by_parent.values():
        siblings.sort(key=lambda n: (n.order_index, n.created_at))

    def to_json(node: ResumeNode) -> dict:
        return {
            "id": str(node.id),
            "resume_id": str(node.resume_id),
            "parent_id": str(node.parent_id) if node.parent_id is not None else None,
            "node_type": node.node_type,
            "title": node.title,
            "content": node.content,
            "order_index": node.order_index,
            "metadata": node.metadata_,
            "created_at": node.created_at.isoformat(),
            "updated_at": node.updated_at.isoformat(),
            "children": [to_json(c) for c in by_parent.get(node.id, [])],
        }

    roots = by_parent.get(None, [])
    return [to_json(r) for r in roots]

