from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DEFAULT_CONFIG
from app.db.deps import get_db_session
from app.db.models import Resume, ResumeNode
from app.llm.factory import build_llm_provider
from app.rag.qdrant_store import QdrantConfig, count_points_for_bank, get_client
from app.rag.retriever import retrieve

router = APIRouter(prefix="/api/resumes", tags=["retrieve_debug"])


class RetrieveDebugRequest(BaseModel):
    jd_text: str = Field(min_length=1)
    top_k: int = Field(default=12, ge=1, le=50)


@router.post("/{resume_id}/retrieve/debug")
async def api_retrieve_debug(
    resume_id: str,
    body: RetrieveDebugRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Phase 4 debug endpoint.

    Phase 4 still uses the legacy Qdrant *chunk* collection (bank_folder_name filtering) for retrieval,
    while Postgres `resume_nodes` is the source-of-truth for the parsed resume tree.

    This endpoint reports:
    - Postgres node shape (node_types counts)
    - Qdrant chunk points count for the resume slug
    - Retrieved chunk sample (ids + evidence_ids)
    """
    try:
        rid = uuid.UUID(resume_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid resume_id UUID")

    resume = (await session.execute(select(Resume).where(Resume.id == rid))).scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    nodes = (await session.execute(select(ResumeNode).where(ResumeNode.resume_id == rid))).scalars().all()
    node_types: dict[str, int] = {}
    for n in nodes:
        node_types[n.node_type] = node_types.get(n.node_type, 0) + 1

    qurl = (DEFAULT_CONFIG.qdrant_url or "").strip()
    if not qurl:
        raise HTTPException(status_code=400, detail="QDRANT_URL is not set")

    qc = QdrantConfig(url=qurl, collection=DEFAULT_CONFIG.qdrant_collection)
    client = get_client(qc)
    qdrant_points_count = count_points_for_bank(client=client, collection=qc.collection, bank_folder_name=resume.slug)

    llm = build_llm_provider(DEFAULT_CONFIG)
    chunks = retrieve(query=body.jd_text, bank_folder_name=resume.slug, llm=llm, top_k=body.top_k)
    retrieved_chunk_ids = [c.chunk_id for c in chunks]
    retrieved_evidence_ids: list[str] = []
    for c in chunks:
        eids = c.metadata.get("evidence_ids")
        if isinstance(eids, list):
            retrieved_evidence_ids.extend([str(x) for x in eids if str(x).strip()])
    retrieved_evidence_ids = list(dict.fromkeys(retrieved_evidence_ids))

    return {
        "resume_id": str(resume.id),
        "resume_slug": resume.slug,
        "node_types": node_types,
        "qdrant_collection": qc.collection,
        "qdrant_points_count": qdrant_points_count,
        "retrieved_chunk_ids": retrieved_chunk_ids,
        "retrieved_evidence_ids": retrieved_evidence_ids,
        "retrieved_chunks_preview": [
            {"chunk_id": c.chunk_id, "score": c.score, "evidence_ids": c.metadata.get("evidence_ids", [])} for c in chunks[:5]
        ],
        "notes": "Phase 4 retrieval debug (Qdrant chunk store). Phase 5 resume_nodes semantic retrieval is not enabled on this branch.",
    }

