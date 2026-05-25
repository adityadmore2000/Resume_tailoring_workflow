from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import HTTPException

import app.api.routers.banks as banks_mod
import app.bank_generator.bank_builder as bank_builder_mod
import app.config as config_mod
import app.rag.ingest as ingest_mod
import app.rag.retriever as retriever_mod
from app.bank_generator.bank_registry import BankRegistry, BankRegistryEntry
from app.rag.qdrant_store import QdrantConfig, count_points_for_bank, ensure_collection, get_client


def _set_cfg(monkeypatch, *, data_root: Path, collection: str):
    cfg = replace(config_mod.DEFAULT_CONFIG, data_root=str(data_root), qdrant_url=":memory:", qdrant_collection=collection)
    monkeypatch.setattr(config_mod, "DEFAULT_CONFIG", cfg)
    monkeypatch.setattr(bank_builder_mod, "DEFAULT_CONFIG", cfg)
    monkeypatch.setattr(banks_mod, "DEFAULT_CONFIG", cfg)
    monkeypatch.setattr(ingest_mod, "DEFAULT_CONFIG", cfg)
    monkeypatch.setattr(retriever_mod, "DEFAULT_CONFIG", cfg)
    return cfg


def test_delete_bank_removes_registry_files_and_qdrant_points(tmp_path: Path, monkeypatch):
    cfg = _set_cfg(monkeypatch, data_root=tmp_path / "data", collection="del")
    data_root = Path(cfg.data_root)

    reg = BankRegistry(data_root / "experience_bank" / "banks_registry.json")
    reg.upsert(
        BankRegistryEntry(
            bank_folder_name="bank_a",
            display_name="Bank A",
            original_resume_path=str(data_root / "uploads" / "bank_a" / "resume.tex"),
            experience_bank_path=str(data_root / "experience_bank" / "bank_a"),
            vector_store_path=str(data_root / "vector_store" / "bank_a"),
            notes="",
        )
    )
    reg.upsert(
        BankRegistryEntry(
            bank_folder_name="bank_b",
            display_name="Bank B",
            original_resume_path=str(data_root / "uploads" / "bank_b" / "resume.tex"),
            experience_bank_path=str(data_root / "experience_bank" / "bank_b"),
            vector_store_path=str(data_root / "vector_store" / "bank_b"),
            notes="",
        )
    )

    # Create on-disk folders for bank_a.
    (data_root / "uploads" / "bank_a").mkdir(parents=True, exist_ok=True)
    (data_root / "experience_bank" / "bank_a").mkdir(parents=True, exist_ok=True)
    (data_root / "vector_store" / "bank_a").mkdir(parents=True, exist_ok=True)

    # Seed qdrant points for bank_a + bank_b.
    from qdrant_client.http.models import PointStruct
    import uuid

    qc = QdrantConfig(url=cfg.qdrant_url or "", collection=cfg.qdrant_collection)
    client = get_client(qc)
    ensure_collection(client=client, collection=qc.collection, vector_size=8)
    client.upsert(
        collection_name=qc.collection,
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=[0.1] * 8,
                payload={"bank_folder_name": "bank_a", "chunk_id": "a1", "text": "x", "evidence_ids": []},
            ),
            PointStruct(
                id=str(uuid.uuid4()),
                vector=[0.1] * 8,
                payload={"bank_folder_name": "bank_b", "chunk_id": "b1", "text": "y", "evidence_ids": []},
            ),
        ],
    )
    assert count_points_for_bank(client=client, collection=qc.collection, bank_folder_name="bank_a") == 1

    res = banks_mod.api_delete_bank("bank_a")
    assert res["deleted"] is True
    assert res["bank_name"] == "bank_a"
    assert res["deleted_files"] is True
    assert res["deleted_qdrant_points"] == 1

    # bank_a removed; bank_b remains.
    remaining = {e.bank_folder_name for e in reg.load()}
    assert remaining == {"bank_b"}
    assert not (data_root / "experience_bank" / "bank_a").exists()
    assert not (data_root / "vector_store" / "bank_a").exists()
    assert not (data_root / "uploads" / "bank_a").exists()
    assert count_points_for_bank(client=client, collection=qc.collection, bank_folder_name="bank_a") == 0
    assert count_points_for_bank(client=client, collection=qc.collection, bank_folder_name="bank_b") == 1


def test_delete_bank_rejects_path_traversal(monkeypatch):
    _set_cfg(monkeypatch, data_root=Path("data"), collection="del2")
    with pytest.raises(HTTPException) as e:
        banks_mod.api_delete_bank("../oops")
    assert e.value.status_code == 400


def test_delete_bank_returns_404_for_missing(tmp_path: Path, monkeypatch):
    _set_cfg(monkeypatch, data_root=tmp_path / "data", collection="del3")
    with pytest.raises(HTTPException) as e:
        banks_mod.api_delete_bank("missing_bank")
    assert e.value.status_code == 404
