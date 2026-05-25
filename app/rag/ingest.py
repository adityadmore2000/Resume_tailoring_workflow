from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from qdrant_client.http.models import PointStruct

from app.config import DEFAULT_CONFIG
from app.llm import LLMError, LLMProvider
from app.rag.chunker import chunk_markdown_file
from app.rag.qdrant_store import QdrantConfig, ensure_collection, get_client, upsert_points


@dataclass(frozen=True)
class VectorStoreRecord:
    chunk_id: str
    text: str
    embedding: list[float] | None
    metadata: dict[str, object]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


def ingest_experience_bank(
    *,
    bank_folder_name: str,
    experience_bank_dir: Path,
    vector_store_dir: Path,
    llm: LLMProvider,
) -> tuple[int, list[str]]:
    """
    Ingests markdown files into a JSONL "vector store".
    If embeddings fail, stores embedding=None and relies on keyword-only retrieval.
    """
    warnings: list[str] = []
    md_files = sorted([p for p in experience_bank_dir.rglob("*.md") if p.is_file()])
    records: list[VectorStoreRecord] = []

    for p in md_files:
        base_md = {"bank_folder_name": bank_folder_name, "path": str(p)}
        chunks = chunk_markdown_file(p, base_metadata=base_md)
        for c in chunks:
            emb = None
            try:
                emb = llm.embed_text(c.text[:8000])
            except LLMError as e:
                warnings.append(f"Embeddings unavailable for {p.name}: {e}. Falling back to keyword-only retrieval.")
                emb = None
            records.append(VectorStoreRecord(chunk_id=c.chunk_id, text=c.text, embedding=emb, metadata=c.metadata))

    vector_store_dir.mkdir(parents=True, exist_ok=True)
    out_path = vector_store_dir / "index.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps({"chunk_id": r.chunk_id, "text": r.text, "embedding": r.embedding, "metadata": r.metadata}) + "\n")

    # Optional: also upsert embeddings into Qdrant for faster semantic search.
    qdrant_url = (DEFAULT_CONFIG.qdrant_url or "").strip()
    if qdrant_url:
        with_emb = [r for r in records if r.embedding]
        if with_emb:
            dim = len(with_emb[0].embedding or [])
            if dim > 0:
                try:
                    qc = QdrantConfig(url=qdrant_url, collection=DEFAULT_CONFIG.qdrant_collection)
                    client = get_client(qc)
                    ensure_collection(client=client, collection=qc.collection, vector_size=dim)
                    points: list[PointStruct] = []
                    for r in with_emb:
                        emb = r.embedding
                        if not emb or len(emb) != dim:
                            continue
                        points.append(
                            PointStruct(
                                id=r.chunk_id,
                                vector=emb,
                                payload={
                                    "bank_folder_name": bank_folder_name,
                                    "text": r.text,
                                    "metadata": r.metadata,
                                },
                            )
                        )
                    upsert_points(client=client, collection=qc.collection, points=points)
                except Exception as e:
                    warnings.append(f"Qdrant upsert failed: {e}. Falling back to local JSONL vector store only.")

    return len(records), sorted(set(warnings))
