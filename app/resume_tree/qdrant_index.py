from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchAny, MatchValue, PointIdsList, PointStruct

from app.config import DEFAULT_CONFIG
from app.db.models import ResumeNode
from app.rag.qdrant_store import QdrantConfig, ensure_collection, get_client, upsert_points


SEARCHABLE_NODE_TYPES: set[str] = {
    "bullet",
    "summary",
    "project",
    "experience",
    "skill_group",
    "capability",
    "reusable_block",
}


def nodes_collection_name() -> str:
    v = (os.environ.get("QDRANT_RESUME_NODES_COLLECTION") or "").strip()
    if v:
        return v
    # Keep separate from the chunk collection to avoid schema collisions.
    return f"{DEFAULT_CONFIG.qdrant_collection}_resume_nodes"


@dataclass(frozen=True)
class ResumeNodesIndexConfig:
    url: str
    collection: str


class QdrantResumeNodesIndex:
    def __init__(self, *, cfg: ResumeNodesIndexConfig, llm) -> None:
        self._cfg = cfg
        self._llm = llm
        self._client: QdrantClient = get_client(QdrantConfig(url=cfg.url, collection=cfg.collection))

    def embed(self, text: str) -> list[float]:
        return self._llm.embed_text(text)

    def _is_searchable(self, node: ResumeNode) -> bool:
        if node.node_type not in SEARCHABLE_NODE_TYPES:
            return False
        md = node.metadata_ or {}
        if isinstance(md, dict) and md.get("searchable") is False:
            return False
        return True

    def _semantic_text(self, node: ResumeNode) -> str:
        md = node.metadata_ or {}
        src = md.get("source_text") if isinstance(md, dict) else None
        if isinstance(src, str) and src.strip():
            return src.strip()
        parts: list[str] = []
        if node.title:
            parts.append(node.title)
        if node.content is not None:
            try:
                parts.append(json.dumps(node.content, ensure_ascii=False, sort_keys=True))
            except Exception:
                parts.append(str(node.content))
        return "\n".join([p for p in parts if p.strip()])[:8000]

    def _payload(self, node: ResumeNode) -> dict[str, object]:
        md = node.metadata_ or {}
        tags = md.get("tags") if isinstance(md, dict) else None
        tools = md.get("tools") if isinstance(md, dict) else None
        skills = md.get("skills") if isinstance(md, dict) else None
        evidence_ids = md.get("evidence_ids") if isinstance(md, dict) else None
        return {
            "node_id": str(node.id),
            "resume_id": str(node.resume_id),
            "parent_id": str(node.parent_id) if node.parent_id is not None else None,
            "node_type": node.node_type,
            "title": node.title,
            "tags": tags if isinstance(tags, list) else [],
            "tools": tools if isinstance(tools, list) else [],
            "skills": skills if isinstance(skills, list) else [],
            "evidence_ids": evidence_ids if isinstance(evidence_ids, list) else [],
        }

    def upsert_node(self, node: ResumeNode) -> None:
        if not self._is_searchable(node):
            self.delete_nodes([node.id])
            return
        text = self._semantic_text(node)
        vec = self._llm.embed_text(text[:4000])
        ensure_collection(client=self._client, collection=self._cfg.collection, vector_size=len(vec))
        upsert_points(
            client=self._client,
            collection=self._cfg.collection,
            points=[PointStruct(id=str(node.id), vector=vec, payload=self._payload(node))],
        )

    def delete_nodes(self, node_ids: list[uuid.UUID]) -> None:
        if not node_ids:
            return
        ids = [str(i) for i in node_ids]
        try:
            self._client.delete(collection_name=self._cfg.collection, points_selector=PointIdsList(points=ids))
        except Exception:
            # Collection might not exist yet; treat as already-deleted.
            return

    def delete_by_resume_id(self, resume_id: uuid.UUID) -> None:
        f = Filter(must=[FieldCondition(key="resume_id", match=MatchValue(value=str(resume_id)))])
        try:
            self._client.delete(collection_name=self._cfg.collection, points_selector=f)
        except Exception:
            return

    def search(self, *, resume_id: uuid.UUID, query_vector: list[float], limit: int) -> list[dict[str, object]]:
        if query_vector:
            ensure_collection(client=self._client, collection=self._cfg.collection, vector_size=len(query_vector))
        f = Filter(must=[FieldCondition(key="resume_id", match=MatchValue(value=str(resume_id)))])
        res = self._client.query_points(
            collection_name=self._cfg.collection,
            query=query_vector,
            query_filter=f,
            limit=limit,
            with_payload=True,
        )
        out: list[dict[str, object]] = []
        for p in (res.points or []):
            payload = getattr(p, "payload", None) or {}
            out.append({"node_id": str(payload.get("node_id") or p.id), "score": float(getattr(p, "score", 0.0) or 0.0), "payload": payload})
        return out
