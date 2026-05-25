from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)


@dataclass(frozen=True)
class QdrantConfig:
    url: str
    collection: str


def get_client(cfg: QdrantConfig) -> QdrantClient:
    return QdrantClient(url=cfg.url)


def ensure_collection(*, client: QdrantClient, collection: str, vector_size: int) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if collection in existing:
        return
    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def upsert_points(
    *,
    client: QdrantClient,
    collection: str,
    points: list[PointStruct],
) -> None:
    if not points:
        return
    client.upsert(collection_name=collection, points=points)


def search(
    *,
    client: QdrantClient,
    collection: str,
    query_vector: list[float],
    bank_folder_name: str,
    limit: int,
) -> list[dict[str, object]]:
    f = Filter(must=[FieldCondition(key="bank_folder_name", match=MatchValue(value=bank_folder_name))])
    hits = client.search(
        collection_name=collection,
        query_vector=query_vector,
        query_filter=f,
        limit=limit,
        with_payload=True,
    )
    out: list[dict[str, object]] = []
    for h in hits:
        payload = h.payload or {}
        out.append(
            {
                "chunk_id": str(h.id),
                "score": float(h.score or 0.0),
                "text": payload.get("text", ""),
                "metadata": payload.get("metadata", {}),
            }
        )
    return out

