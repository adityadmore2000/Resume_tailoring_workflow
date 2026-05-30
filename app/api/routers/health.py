from __future__ import annotations

from fastapi import APIRouter

from app.config import AppConfig
from app.qdrant import QdrantConfig, get_client, healthcheck
from app.resume_tree.qdrant_index import nodes_collection_name

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict:
    cfg = AppConfig.from_env()
    qdrant_url = (cfg.qdrant_url or "").strip()
    if not qdrant_url:
        qdrant_ok = False
        qdrant_error = "QDRANT_URL not set"
    else:
        try:
            client = get_client(QdrantConfig(url=qdrant_url))
            healthcheck(client=client)
            qdrant_ok = True
            qdrant_error = None
        except Exception as e:
            qdrant_ok = False
            qdrant_error = str(e)
    return {"ok": True, "qdrant": {"ok": qdrant_ok, "resume_nodes_collection": nodes_collection_name(), "error": qdrant_error}}
