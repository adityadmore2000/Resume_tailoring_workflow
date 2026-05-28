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


_MEMORY_CLIENT: QdrantClient | None = None


def get_client(cfg: QdrantConfig) -> QdrantClient:
    url = (cfg.url or "").strip()
    if url == ":memory:":
        global _MEMORY_CLIENT
        if _MEMORY_CLIENT is None:
            _MEMORY_CLIENT = QdrantClient(location=":memory:")
        return _MEMORY_CLIENT
    return QdrantClient(url=url)


def healthcheck(*, client: QdrantClient) -> None:
    # Any API call that requires a round-trip is fine; keep it lightweight.
    client.get_collections()


def ensure_collection(*, client: QdrantClient, collection: str, vector_size: int) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if collection in existing:
        return
    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def ensure_collection_exists(*, client: QdrantClient, collection: str, vector_size: int) -> None:
    """
    Idempotent guard for operations that assume a collection exists.

    Creates the collection if missing, no-ops if already present.
    """
    if vector_size <= 0:
        raise ValueError("vector_size must be > 0")
    ensure_collection(client=client, collection=collection, vector_size=vector_size)


def _collection_missing_error(exc: Exception) -> bool:
    msg = str(exc).casefold()
    return "doesn't exist" in msg or "not found" in msg or "404" in msg


def _collection_exists(*, client: QdrantClient, collection: str) -> bool:
    try:
        existing = {c.name for c in client.get_collections().collections}
        return collection in existing
    except Exception:
        return False


def upsert_points(
    *,
    client: QdrantClient,
    collection: str,
    points: list[PointStruct],
) -> None:
    if not points:
        return
    vec = getattr(points[0], "vector", None)
    if isinstance(vec, list) and vec:
        ensure_collection_exists(client=client, collection=collection, vector_size=len(vec))
    client.upsert(collection_name=collection, points=points)


def delete_points_for_bank(*, client: QdrantClient, collection: str, bank_folder_name: str) -> None:
    if not _collection_exists(client=client, collection=collection):
        return
    f = Filter(must=[FieldCondition(key="bank_folder_name", match=MatchValue(value=bank_folder_name))])
    try:
        client.delete(collection_name=collection, points_selector=f)
    except Exception as e:
        if _collection_missing_error(e):
            return
        raise


def count_points_for_bank(*, client: QdrantClient, collection: str, bank_folder_name: str) -> int:
    if not _collection_exists(client=client, collection=collection):
        return 0
    f = Filter(must=[FieldCondition(key="bank_folder_name", match=MatchValue(value=bank_folder_name))])
    try:
        res = client.count(collection_name=collection, count_filter=f, exact=True)
        return int(res.count or 0)
    except Exception as e:
        if _collection_missing_error(e):
            return 0
        raise


def search(
    *,
    client: QdrantClient,
    collection: str,
    query_vector: list[float],
    bank_folder_name: str,
    limit: int,
) -> list[dict[str, object]]:
    if query_vector:
        ensure_collection_exists(client=client, collection=collection, vector_size=len(query_vector))
    f = Filter(must=[FieldCondition(key="bank_folder_name", match=MatchValue(value=bank_folder_name))])
    try:
        res = client.query_points(
            collection_name=collection,
            query=query_vector,
            query_filter=f,
            limit=limit,
            with_payload=True,
        )
    except Exception as e:
        if _collection_missing_error(e):
            return []
        raise
    out: list[dict[str, object]] = []
    for h in (res.points or []):
        payload = getattr(h, "payload", None) or {}
        score = float(getattr(h, "score", 0.0) or 0.0)
        out.append(
            {
                "chunk_id": str(payload.get("chunk_id") or h.id),
                "score": score,
                "text": payload.get("text", ""),
                "metadata": payload,
            }
        )
    return out
