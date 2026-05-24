from __future__ import annotations

import json
from pathlib import Path

from app.ui.api.bank_preview_api import compute_stats, tree_for_expected_dirs
from app.ui.api.experience_banks_api import read_bank_file


def test_tree_for_expected_dirs_includes_expected_keys(tmp_path: Path):
    bank = tmp_path / "bank"
    (bank / "metadata").mkdir(parents=True, exist_ok=True)
    (bank / "projects").mkdir(parents=True, exist_ok=True)
    (bank / "projects" / "a.md").write_text("# x", encoding="utf-8")
    tree = tree_for_expected_dirs(bank)
    assert "projects" in tree
    assert any(p.name == "a.md" for p in tree["projects"])


def test_compute_stats_counts_chunks_scoped_to_bank(tmp_path: Path):
    bank = tmp_path / "bank"
    vec = tmp_path / "vec"
    (bank / "metadata").mkdir(parents=True, exist_ok=True)
    (vec).mkdir(parents=True, exist_ok=True)
    # fake index.jsonl with two banks
    rows = [
        {"chunk_id": "c1", "text": "t", "embedding": None, "metadata": {"bank_folder_name": "b1"}},
        {"chunk_id": "c2", "text": "t", "embedding": None, "metadata": {"bank_folder_name": "b2"}},
    ]
    (vec / "index.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    s = compute_stats(bank, vec, "b1")
    assert s.total_chunks == 1


def test_read_bank_file_rejects_traversal(tmp_path: Path, monkeypatch):
    # Create a fake data root structure.
    data = tmp_path / "data"
    (data / "experience_bank" / "bank_a" / "metadata").mkdir(parents=True, exist_ok=True)
    (data / "experience_bank" / "bank_a" / "metadata" / "x.md").write_text("# Title", encoding="utf-8")
    # OK read
    rel, title, content = read_bank_file("bank_a", "metadata/x.md", data_root=data)
    assert title == "Title"
    # Traversal rejected
    import pytest

    with pytest.raises(Exception):
        read_bank_file("bank_a", "../uploads/bank_a/resume.tex", data_root=data)
