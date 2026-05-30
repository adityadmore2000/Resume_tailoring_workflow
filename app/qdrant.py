from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams


@dataclass(frozen=True)
class QdrantConfig:
    """
    Shared Qdrant client configuration.

    Note: collection naming is handled by the caller (e.g. resume_nodes index).
    """

    url: str


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
    client.get_collections()


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
    vec = getattr(points[0], "vector", None)
    if isinstance(vec, list) and vec:
        ensure_collection(client=client, collection=collection, vector_size=len(vec))
    client.upsert(collection_name=collection, points=points)

