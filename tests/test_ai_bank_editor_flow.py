from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

import app.bank_editing.service as svc
import app.config as config_mod
from app.bank_editing.models import BankEditProposeRequest
from app.bank_generator.bank_registry import BankRegistry, BankRegistryEntry


def _set_cfg(monkeypatch, *, data_root: Path):
    cfg = replace(config_mod.DEFAULT_CONFIG, data_root=str(data_root), qdrant_url="")
    monkeypatch.setattr(config_mod, "DEFAULT_CONFIG", cfg)
    monkeypatch.setattr(svc, "DEFAULT_CONFIG", cfg)
    return cfg


def test_propose_does_not_apply_and_apply_requires_validation_pass(tmp_path: Path, monkeypatch):
    cfg = _set_cfg(monkeypatch, data_root=tmp_path / "data")
    data_root = Path(cfg.data_root)

    bank = "bank_a"
    bank_dir = data_root / "experience_bank" / bank
    (bank_dir / "work_experience").mkdir(parents=True, exist_ok=True)
    reg = BankRegistry(data_root / "experience_bank" / "banks_registry.json")
    reg.upsert(
        BankRegistryEntry(
            bank_folder_name=bank,
            display_name="Bank A",
            original_resume_path="x",
            experience_bank_path=str(bank_dir),
            vector_store_path=str(data_root / "vector_store" / bank),
            notes="",
        )
    )

    md_path = bank_dir / "work_experience" / "w1.md"
    md_path.write_text(
        "# Role\n\n## Overview\n- Date range: 01/2020 - 12/2020\n- Company: Neilsoft\n\n## Evidence (from resume)\n- E1\n\n## Resume-ready reusable bullets\n- (Generated later; must reference evidence_ids)\n\n## Limitations / unclear areas\n- Unclear\n",
        encoding="utf-8",
    )

    before = md_path.read_text(encoding="utf-8")
    prop = svc.propose_bank_edit(
        bank_name=bank,
        req=BankEditProposeRequest(instruction="Rewrite the bullet to be more GenAI relevant.", target_record_id="work_experience/w1.md"),
    )
    assert prop.proposal_id
    assert md_path.read_text(encoding="utf-8") == before  # not applied automatically
    assert prop.validation.status in {"passed", "needs_review", "failed"}

    # Unsupported claim should fail validation.
    prop2 = svc.propose_bank_edit(
        bank_name=bank,
        req=BankEditProposeRequest(instruction="Add AWS and Kubernetes deployment claims.", target_record_id="work_experience/w1.md"),
    )
    assert prop2.validation.status == "failed"
    applied2 = svc.apply_bank_edit(bank_name=bank, proposal_id=prop2.proposal_id)
    assert applied2.applied is False
    assert md_path.read_text(encoding="utf-8") == before


def test_apply_updates_bank_and_creates_history(tmp_path: Path, monkeypatch):
    cfg = _set_cfg(monkeypatch, data_root=tmp_path / "data")
    data_root = Path(cfg.data_root)

    bank = "bank_a"
    bank_dir = data_root / "experience_bank" / bank
    (bank_dir / "work_experience").mkdir(parents=True, exist_ok=True)
    reg = BankRegistry(data_root / "experience_bank" / "banks_registry.json")
    reg.upsert(
        BankRegistryEntry(
            bank_folder_name=bank,
            display_name="Bank A",
            original_resume_path="x",
            experience_bank_path=str(bank_dir),
            vector_store_path=str(data_root / "vector_store" / bank),
            notes="",
        )
    )

    md_path = bank_dir / "work_experience" / "w1.md"
    md_path.write_text(
        "# Role\n\n## Overview\n- Date range: 01/2020 - 12/2020\n- Company: Neilsoft\n\n## Evidence (from resume)\n- E1\n\n## Resume-ready reusable bullets\n- (Generated later; must reference evidence_ids)\n\n## Limitations / unclear areas\n- Unclear\n",
        encoding="utf-8",
    )

    prop = svc.propose_bank_edit(
        bank_name=bank,
        req=BankEditProposeRequest(
            instruction="Rewrite the Neilsoft bullet to sound more GenAI relevant but do not add fake skills.",
            target_record_id="work_experience/w1.md",
        ),
    )
    assert prop.validation.status == "passed"

    applied = svc.apply_bank_edit(bank_name=bank, proposal_id=prop.proposal_id)
    assert applied.applied is True
    after = md_path.read_text(encoding="utf-8")
    assert "(Proposed)" in after
    assert "Neilsoft" in after  # immutable field preserved
    assert "01/2020 - 12/2020" in after

    hist = svc.list_bank_edit_history(bank_name=bank)
    assert hist.history
    assert any(h.proposal_id == prop.proposal_id for h in hist.history)


def test_validator_rejects_immutable_field_changes():
    from app.bank_editing.validator import validate_proposed_change

    old = "## Overview\n- Company: Neilsoft\n\n## Resume-ready reusable bullets\n- x\n\n## Limitations\n- y\n"
    new = "## Overview\n- Company: NotNeilsoft\n\n## Resume-ready reusable bullets\n- x\n\n## Limitations\n- y\n"
    v = validate_proposed_change(old_content=old, new_content=new, evidence_ids=["E1"])
    assert v.status == "failed"
    assert v.immutable_field_changes

