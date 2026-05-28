from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

import app.config as config_mod
import app.rag.ingest as ingest_mod
import app.rag.retriever as retriever_mod
from app.rag.ingest import ingest_experience_bank
from app.rag.qdrant_store import QdrantConfig, count_points_for_bank, get_client, healthcheck, upsert_points


class DummyLLM:
    def __init__(self, dim: int = 8):
        self._dim = dim

    def embed_text(self, text: str) -> list[float]:
        # Stable embedding with correct size (content not important for tests).
        return [0.1] * self._dim


def _set_in_memory_qdrant(monkeypatch, *, collection: str) -> None:
    cfg = replace(config_mod.DEFAULT_CONFIG, qdrant_url=":memory:", qdrant_collection=collection)
    monkeypatch.setattr(config_mod, "DEFAULT_CONFIG", cfg)
    monkeypatch.setattr(ingest_mod, "DEFAULT_CONFIG", cfg)
    monkeypatch.setattr(retriever_mod, "DEFAULT_CONFIG", cfg)


def test_qdrant_healthcheck_works(monkeypatch):
    _set_in_memory_qdrant(monkeypatch, collection="hc")
    qc = QdrantConfig(url=config_mod.DEFAULT_CONFIG.qdrant_url or "", collection=config_mod.DEFAULT_CONFIG.qdrant_collection)
    client = get_client(qc)
    healthcheck(client=client)


def test_ingestion_writes_points_to_qdrant_and_creates_no_jsonl(tmp_path: Path, monkeypatch):
    _set_in_memory_qdrant(monkeypatch, collection="ingest")
    bank_dir = tmp_path / "bank"
    (bank_dir / "projects").mkdir(parents=True, exist_ok=True)
    (bank_dir / "projects" / "p1.md").write_text("# Project\n- Company: Acme\n- Date range: 01/2024 - 02/2024\n", encoding="utf-8")

    llm = DummyLLM(dim=8)
    n, warnings = ingest_experience_bank(bank_folder_name="bank_a", experience_bank_dir=bank_dir, llm=llm)
    assert n > 0
    assert warnings == []

    # Ensure no legacy JSONL index gets created anywhere in the bank folder.
    assert not list(bank_dir.rglob("index.jsonl"))

    qc = QdrantConfig(url=config_mod.DEFAULT_CONFIG.qdrant_url or "", collection=config_mod.DEFAULT_CONFIG.qdrant_collection)
    client = get_client(qc)
    assert count_points_for_bank(client=client, collection=qc.collection, bank_folder_name="bank_a") > 0


def test_upsert_auto_creates_collection(monkeypatch):
    _set_in_memory_qdrant(monkeypatch, collection="autocreate")
    qc = QdrantConfig(url=config_mod.DEFAULT_CONFIG.qdrant_url or "", collection=config_mod.DEFAULT_CONFIG.qdrant_collection)
    client = get_client(qc)

    from qdrant_client.http.models import PointStruct
    import uuid

    upsert_points(
        client=client,
        collection=qc.collection,
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=[0.1] * 8,
                payload={"bank_folder_name": "bank_a", "chunk_id": "a1", "text": "x", "evidence_ids": []},
            )
        ],
    )
    assert count_points_for_bank(client=client, collection=qc.collection, bank_folder_name="bank_a") == 1


def test_retrieval_is_scoped_by_bank_folder_name(monkeypatch):
    _set_in_memory_qdrant(monkeypatch, collection="scope")
    qc = QdrantConfig(url=config_mod.DEFAULT_CONFIG.qdrant_url or "", collection=config_mod.DEFAULT_CONFIG.qdrant_collection)
    client = get_client(qc)

    # Seed points for two banks.
    from qdrant_client.http.models import PointStruct
    import uuid

    upsert_points(
        client=client,
        collection=qc.collection,
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=[0.1] * 8,
                payload={
                    "bank_folder_name": "bank_a",
                    "chunk_id": "a1",
                    "text": "python validation pipeline",
                    "source_file": "x.md",
                    "domain": "",
                    "capability": "",
                    "tools": [],
                    "project": "",
                    "company": "",
                    "evidence_ids": [],
                    "metrics_available": False,
                    "created_at": "2026-01-01T00:00:00Z",
                },
            ),
            PointStruct(
                id=str(uuid.uuid4()),
                vector=[0.2] * 8,
                payload={
                    "bank_folder_name": "bank_b",
                    "chunk_id": "b1",
                    "text": "kubernetes deployment",
                    "source_file": "y.md",
                    "domain": "",
                    "capability": "",
                    "tools": [],
                    "project": "",
                    "company": "",
                    "evidence_ids": [],
                    "metrics_available": False,
                    "created_at": "2026-01-01T00:00:00Z",
                },
            ),
        ],
    )

    llm = DummyLLM(dim=8)
    out = retriever_mod.retrieve(query="python validation", bank_folder_name="bank_a", llm=llm, top_k=5)
    assert out
    assert all(c.metadata.get("bank_folder_name") == "bank_a" for c in out)
