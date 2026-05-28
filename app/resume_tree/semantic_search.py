from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ResumeNode
from app.resume_tree.qdrant_index import QdrantResumeNodesIndex
from app.resume_tree.tree_build import build_tree


async def retrieve_relevant_nodes_for_jd(
    *,
    session: AsyncSession,
    index: QdrantResumeNodesIndex,
    resume_id: uuid.UUID,
    jd_text: str,
    top_k: int = 12,
) -> dict:
    qvec = index.embed((jd_text or "")[:4000])
    hits = index.search(resume_id=resume_id, query_vector=qvec, limit=top_k)
    matched_ids = [uuid.UUID(str(h["node_id"])) for h in hits if h.get("node_id")]
    if not matched_ids:
        return {"resume_id": str(resume_id), "matched_node_ids": [], "tree": {"resume_id": str(resume_id), "roots": []}}

    sql = text(
        """
        WITH RECURSIVE anc AS (
          SELECT id, parent_id
          FROM resume_nodes
          WHERE id = ANY(CAST(:ids AS uuid[]))
          UNION ALL
          SELECT rn.id, rn.parent_id
          FROM resume_nodes rn
          JOIN anc a ON rn.id = a.parent_id
        )
        SELECT DISTINCT id FROM anc
        """
    )
    rows = (await session.execute(sql, {"ids": [str(i) for i in matched_ids]})).all()
    all_ids = [uuid.UUID(str(r[0])) for r in rows]

    nodes = (
        await session.execute(
            select(ResumeNode)
            .where(ResumeNode.resume_id == resume_id, ResumeNode.id.in_(all_ids))
            .order_by(ResumeNode.parent_id.nullsfirst(), ResumeNode.order_index, ResumeNode.created_at)
        )
    ).scalars().all()

    return {
        "resume_id": str(resume_id),
        "matched_node_ids": [str(i) for i in matched_ids],
        "tree": {"resume_id": str(resume_id), "roots": build_tree(nodes)},
    }
