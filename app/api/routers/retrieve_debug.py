from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import AppConfig
from app.db.deps import get_db_session
from app.db.models import Resume, ResumeNode
from app.llm.factory import build_llm_provider
from app.resume_tree.qdrant_index import QdrantResumeNodesIndex, ResumeNodesIndexConfig, nodes_collection_name
from app.resume_tree.hierarchy_inference import infer_nodes, is_searchable
from app.tailoring.hierarchy_context import build_tailoring_context

router = APIRouter(prefix="/api/resumes", tags=["retrieve_debug"])
logger = logging.getLogger(__name__)


class RetrieveNodesDebugRequest(BaseModel):
    jd_text: str = Field(min_length=1)
    top_k: int = Field(default=12, ge=1, le=50)


@router.post("/{resume_id}/retrieve_nodes/debug")
async def api_retrieve_nodes_debug(
    resume_id: str,
    body: RetrieveNodesDebugRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Debug endpoint for the resume_nodes semantic retrieval path.
    """
    try:
        rid = uuid.UUID(resume_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid resume_id UUID")

    resume = (await session.execute(select(Resume).where(Resume.id == rid))).scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    nodes = (
        await session.execute(select(ResumeNode).where(ResumeNode.resume_id == rid).order_by(ResumeNode.parent_id.nullsfirst(), ResumeNode.order_index, ResumeNode.created_at))
    ).scalars().all()

    inferred = infer_nodes(nodes)

    cfg = AppConfig.from_env()
    qurl = (cfg.qdrant_url or "").strip()
    qdrant_error: str | None = None
    matched_node_ids: list[uuid.UUID] = []
    if qurl:
        try:
            llm = build_llm_provider(cfg)
            idx = QdrantResumeNodesIndex(cfg=ResumeNodesIndexConfig(url=qurl, collection=nodes_collection_name()), llm=llm)
            # Idempotently index eligible nodes so debug reflects current Postgres state.
            to_delete: list[uuid.UUID] = []
            for n in nodes:
                ok, _reasons = idx.index_decision(n)
                if ok:
                    idx.upsert_node(n)
                else:
                    to_delete.append(n.id)
            if to_delete:
                idx.delete_nodes(to_delete)
            hits = idx.search(resume_id=rid, query_vector=idx.embed(body.jd_text[:4000]), limit=body.top_k)
            for h in hits:
                try:
                    matched_node_ids.append(uuid.UUID(str(h.get("node_id") or "")))
                except Exception:
                    continue
        except Exception as e:
            qdrant_error = str(e)

    context, ctx_debug = build_tailoring_context(nodes=nodes, matched_node_ids=matched_node_ids)

    node_debug: list[dict[str, object]] = []
    ambiguity_events: list[str] = []
    for n in nodes:
        view = inferred.get(n.id)
        eligible, eligible_reasons = is_searchable(n)
        if view is not None and view.ambiguities:
            ambiguity_events.append(f"{n.id}: " + " | ".join(view.ambiguities[:4]))
        node_debug.append(
            {
                "node_id": str(n.id),
                "parent_id": str(n.parent_id) if n.parent_id is not None else None,
                "node_type": n.node_type,
                "section_label": view.section_label if view is not None else "other",
                "inferred_semantic_role": view.inferred_semantic_role if view is not None else "",
                "searchable": bool((n.metadata_ or {}).get("searchable") is True) if isinstance(n.metadata_, dict) else False,
                "index_eligible": eligible,
                "index_decision": "eligible" if eligible else "skipped",
                "index_reasons": [] if eligible else eligible_reasons,
                "source_text_preview": (((n.metadata_ or {}).get("source_text") if isinstance(n.metadata_, dict) else "") or "")[:280],
                "ambiguities": view.ambiguities if view is not None else [],
            }
        )

    if ambiguity_events:
        logger.warning("resume_nodes ambiguity: resume_id=%s count=%s sample=%s", str(resume.id), len(ambiguity_events), ambiguity_events[:5])

    return {
        "resume_id": str(resume.id),
        "resume_slug": resume.slug,
        "qdrant_enabled": bool(qurl),
        "qdrant_url": qurl if qurl else None,
        "qdrant_resume_nodes_collection": nodes_collection_name(),
        "qdrant_error": qdrant_error,
        "matched_node_ids": [str(x) for x in matched_node_ids],
        "context": context,
        "context_debug": ctx_debug,
        "nodes": node_debug,
    }
