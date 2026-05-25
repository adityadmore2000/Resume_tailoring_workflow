from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone
import re
import uuid

from qdrant_client.http.models import PointStruct

from app.config import DEFAULT_CONFIG
from app.config import AppConfig
from app.llm import LLMError, LLMProvider
from app.rag.chunker import chunk_markdown_file
from app.rag.qdrant_store import QdrantConfig, delete_points_for_bank, ensure_collection, get_client, upsert_points


@dataclass(frozen=True)
class VectorStoreRecord:
    chunk_id: str
    text: str
    embedding: list[float] | None
    metadata: dict[str, object]


def ingest_experience_bank(
    *,
    bank_folder_name: str,
    experience_bank_dir: Path,
    llm: LLMProvider,
    cfg: AppConfig | None = None,
) -> tuple[int, list[str]]:
    """
    Ingests markdown files into Qdrant.

    Qdrant is the only supported runtime vector store. This function must not read/write any
    JSONL index files.
    """
    warnings: list[str] = []
    md_files = sorted([p for p in experience_bank_dir.rglob("*.md") if p.is_file()])
    records: list[VectorStoreRecord] = []

    if cfg is None:
        cfg = DEFAULT_CONFIG

    if not (cfg.qdrant_url or "").strip():
        raise RuntimeError("Qdrant is required. Set QDRANT_URL (and optionally QDRANT_COLLECTION).")

    created_at = datetime.now(timezone.utc).isoformat()

    for p in md_files:
        base_md = {"bank_folder_name": bank_folder_name, "path": str(p)}
        chunks = chunk_markdown_file(p, base_metadata=base_md)
        for c in chunks:
            try:
                emb = llm.embed_text(c.text[:8000])
            except LLMError as e:
                raise RuntimeError(f"Embeddings failed for {p.name}: {e}") from e
            records.append(VectorStoreRecord(chunk_id=c.chunk_id, text=c.text, embedding=emb, metadata=c.metadata))

    with_emb = [r for r in records if r.embedding]
    if not with_emb:
        raise RuntimeError("No embeddings were produced; cannot ingest into Qdrant.")

    dim = len(with_emb[0].embedding or [])
    if dim <= 0:
        raise RuntimeError("Invalid embedding dimension; cannot ingest into Qdrant.")

    qc = QdrantConfig(url=(cfg.qdrant_url or "").strip(), collection=cfg.qdrant_collection)
    client = get_client(qc)
    ensure_collection(client=client, collection=qc.collection, vector_size=dim)

    # Delete any existing points for this bank to avoid duplicates during rebuild/re-ingest.
    delete_points_for_bank(client=client, collection=qc.collection, bank_folder_name=bank_folder_name)

    def _extract_field(pattern: str, text: str) -> str:
        m = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        return (m.group(1).strip() if m else "").strip()

    points: list[PointStruct] = []
    for r in with_emb:
        emb = r.embedding
        if not emb or len(emb) != dim:
            raise RuntimeError("Inconsistent embedding dimensions; aborting ingestion.")

        text = r.text or ""
        source_file = str(r.metadata.get("source_file") or r.metadata.get("path") or "")
        # Best-effort extraction from bank markdown conventions.
        domain = _extract_field(r"^\s*-\s*Subtitle/domain:\s*(.+?)\s*$", text)
        capability = _extract_field(r"^\s*-\s*Name:\s*(.+?)\s*$", text)
        company = _extract_field(r"^\s*-\s*Company:\s*(.+?)\s*$", text)
        project = _extract_field(r"^\s*-\s*Project:\s*(.+?)\s*$", text)
        tools_raw = _extract_field(r"^\s*-\s*Technologies/tools explicitly mentioned:\s*(.+?)\s*$", text)
        tools = [t.strip() for t in re.split(r"[,;/]", tools_raw) if t.strip()] if tools_raw else []

        evidence_ids = r.metadata.get("evidence_ids")
        if not isinstance(evidence_ids, list):
            evidence_ids = []
        evidence_ids = [str(x) for x in evidence_ids]

        metrics_available = bool(r.metadata.get("metrics_available"))

        payload: dict[str, object] = {
            "bank_folder_name": bank_folder_name,
            "chunk_id": r.chunk_id,
            "text": text,
            "source_file": source_file,
            "domain": domain,
            "capability": capability,
            "tools": tools,
            "project": project,
            "company": company,
            "evidence_ids": evidence_ids,
            "metrics_available": metrics_available,
            "created_at": created_at,
        }
        # Qdrant point IDs must be UUID (or int). Keep the human-readable `chunk_id` in payload.
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"resume-tailor:{bank_folder_name}:{r.chunk_id}"))
        points.append(PointStruct(id=point_id, vector=emb, payload=payload))

    upsert_points(client=client, collection=qc.collection, points=points)

    return len(records), sorted(set(warnings))
