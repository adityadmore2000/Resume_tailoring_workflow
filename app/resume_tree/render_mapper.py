from __future__ import annotations

import uuid
from collections import defaultdict

from app.db.models import Resume, ResumeNode
from app.resume_tree.renderable import RenderableNode, RenderableResume


def resume_nodes_to_renderable(*, resume: Resume, nodes: list[ResumeNode]) -> RenderableResume:
    """
    Convert flat Postgres resume_nodes into an in-memory tree suitable for rendering.

    This is intentionally generic:
    - node_type is treated as structural
    - metadata is carried through without requiring section-specific schemas
    """
    by_id: dict[uuid.UUID, RenderableNode] = {}
    children_by_parent: dict[uuid.UUID | None, list[RenderableNode]] = defaultdict(list)

    for n in nodes:
        rn = RenderableNode(
            node_id=n.id,
            parent_id=n.parent_id,
            node_type=n.node_type,
            title=n.title,
            content=n.content if isinstance(n.content, dict) else (n.content if n.content is None else dict(n.content)),
            metadata=n.metadata_ if isinstance(n.metadata_, dict) else {},
            order_index=int(n.order_index or 0),
            children=[],
        )
        by_id[n.id] = rn
        children_by_parent[n.parent_id].append(rn)

    # Stable order: order_index then creation order (already applied in DB query), but keep deterministic here too.
    for siblings in children_by_parent.values():
        siblings.sort(key=lambda x: x.order_index)

    # Attach children.
    for parent_id, kids in children_by_parent.items():
        if parent_id is None:
            continue
        parent = by_id.get(parent_id)
        if parent is None:
            continue
        parent.children = kids

    roots = children_by_parent.get(None, [])
    return RenderableResume(resume_id=resume.id, slug=resume.slug, title=resume.title, roots=roots)

