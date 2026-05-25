from __future__ import annotations

import json
from pathlib import Path

from app.bank_generator.bank_registry import BankRegistry, BankRegistryEntry
from app.ui.api.experience_banks_api import write_bank_file


def test_write_bank_file_creates_backup_and_writes_content(tmp_path: Path):
    data = tmp_path / "data"
    bank_dir = data / "experience_bank" / "bank_a"
    (bank_dir / "metadata").mkdir(parents=True, exist_ok=True)
    target = bank_dir / "metadata" / "notes.md"
    target.write_text("# Notes\nv1\n", encoding="utf-8")

    rel = write_bank_file("bank_a", "metadata/notes.md", content="# Notes\nv2\n", data_root=data)
    assert rel == "metadata/notes.md"
    assert target.read_text(encoding="utf-8") == "# Notes\nv2\n"
    backups = list((bank_dir / "metadata").glob("notes.md.bak.*"))
    assert backups


def test_write_bank_file_validates_json(tmp_path: Path):
    data = tmp_path / "data"
    bank_dir = data / "experience_bank" / "bank_a"
    (bank_dir / "metadata").mkdir(parents=True, exist_ok=True)
    target = bank_dir / "metadata" / "x.json"
    target.write_text("{}", encoding="utf-8")

    try:
        write_bank_file("bank_a", "metadata/x.json", content="{not json", data_root=data)
    except Exception as e:
        assert "Invalid JSON" in str(e)
    else:
        raise AssertionError("Expected JSON validation error")


def test_registry_manual_modified_flag_roundtrip(tmp_path: Path):
    data = tmp_path / "data"
    reg_path = data / "experience_bank" / "banks_registry.json"
    reg = BankRegistry(reg_path)
    entry = BankRegistryEntry(
        bank_folder_name="bank_a",
        display_name="Bank A",
        original_resume_path="x",
        experience_bank_path="y",
        vector_store_path="z",
        notes="",
        manually_modified=False,
    )
    reg.upsert(entry)
    loaded = reg.load()
    assert loaded and loaded[0].manually_modified is False

