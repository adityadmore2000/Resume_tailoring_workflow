from __future__ import annotations

from fastapi import APIRouter

from app.config import DEFAULT_CONFIG
from app.rag.qdrant_store import QdrantConfig, get_client, healthcheck

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict:
    qdrant_url = (DEFAULT_CONFIG.qdrant_url or "").strip()
    qc = QdrantConfig(url=qdrant_url, collection=DEFAULT_CONFIG.qdrant_collection)
    if not qdrant_url:
        qdrant_ok = False
        qdrant_error = "QDRANT_URL not set"
    else:
        try:
            client = get_client(qc)
            healthcheck(client=client)
            qdrant_ok = True
            qdrant_error = None
        except Exception as e:
            qdrant_ok = False
            qdrant_error = str(e)
    return {"ok": True, "qdrant": {"ok": qdrant_ok, "collection": qc.collection, "error": qdrant_error}}
