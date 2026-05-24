from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.llm import LLMError, OllamaClient
from app.rag.chunker import chunk_markdown_file


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
    llm: OllamaClient,
    embedding_model: str,
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
                emb = llm.embed(c.text[:8000], embed_model=embedding_model)
            except LLMError as e:
                warnings.append(f"Embeddings unavailable for {p.name}: {e}. Falling back to keyword-only retrieval.")
                emb = None
            records.append(VectorStoreRecord(chunk_id=c.chunk_id, text=c.text, embedding=emb, metadata=c.metadata))

    vector_store_dir.mkdir(parents=True, exist_ok=True)
    out_path = vector_store_dir / "index.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps({"chunk_id": r.chunk_id, "text": r.text, "embedding": r.embedding, "metadata": r.metadata}) + "\n")

    return len(records), sorted(set(warnings))

