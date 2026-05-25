from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import DEFAULT_CONFIG
from app.llm import LLMProvider
from app.rag.qdrant_store import QdrantConfig, get_client, search as qdrant_search


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    score: float
    metadata: dict[str, object]


def retrieve(
    *,
    query: str,
    bank_folder_name: str,
    llm: LLMProvider,
    top_k: int = 8,
) -> list[RetrievedChunk]:
    """
    Qdrant-only retrieval.

    Bank isolation is enforced by a mandatory Qdrant filter on `bank_folder_name`.
    """
    q_emb: list[float] | None = None
    try:
        q_emb = llm.embed_text(query[:4000])
    except Exception:
        q_emb = None

    if q_emb is None:
        raise RuntimeError("Embeddings unavailable; cannot retrieve from Qdrant-only vector store.")

    qdrant_url = (DEFAULT_CONFIG.qdrant_url or "").strip()
    if not qdrant_url:
        raise RuntimeError("Qdrant is required. Set QDRANT_URL (and optionally QDRANT_COLLECTION).")

    qc = QdrantConfig(url=qdrant_url, collection=DEFAULT_CONFIG.qdrant_collection)
    client = get_client(qc)
    hits = qdrant_search(
        client=client,
        collection=qc.collection,
        query_vector=q_emb,
        bank_folder_name=bank_folder_name,
        limit=top_k,
    )
    out: list[RetrievedChunk] = []
    for h in hits:
        md = h.get("metadata")
        if not isinstance(md, dict):
            md = {}
        out.append(
            RetrievedChunk(
                chunk_id=str(h.get("chunk_id", "")),
                text=str(h.get("text", "")),
                score=float(h.get("score", 0.0) or 0.0),
                metadata=md,
            )
        )
    return out
