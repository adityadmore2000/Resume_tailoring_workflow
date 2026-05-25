from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.bank_editing.models import BankEditHistoryItem, BankEditProposeRequest, ProposedChange, ValidationResult


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ChangeProposal:
    proposal_id: str
    bank_name: str
    instruction: str
    target_records: list[dict]
    proposed_changes: list[ProposedChange]
    validation: ValidationResult
    status: str  # proposed|applied|rejected
    created_at: str
    updated_at: str

    def to_json(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "bank_name": self.bank_name,
            "instruction": self.instruction,
            "target_records": self.target_records,
            "proposed_changes": [c.model_dump() for c in self.proposed_changes],
            "validation": self.validation.model_dump(),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_json(d: dict) -> "ChangeProposal":
        return ChangeProposal(
            proposal_id=str(d.get("proposal_id")),
            bank_name=str(d.get("bank_name")),
            instruction=str(d.get("instruction") or ""),
            target_records=list(d.get("target_records") or []),
            proposed_changes=[ProposedChange.model_validate(x) for x in (d.get("proposed_changes") or [])],
            validation=ValidationResult.model_validate(d.get("validation") or {}),
            status=str(d.get("status") or "proposed"),
            created_at=str(d.get("created_at") or ""),
            updated_at=str(d.get("updated_at") or ""),
        )


@dataclass(frozen=True)
class ChangeProposalRepository:
    root_dir: Path

    def _proposal_dir(self, bank_name: str) -> Path:
        d = self.root_dir / "experience_bank" / bank_name / "metadata" / "ai_bank_editor"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _history_path(self, bank_name: str) -> Path:
        return self._proposal_dir(bank_name) / "history.json"

    def create(self, *, bank_name: str, req: BankEditProposeRequest, target_records: list[dict], changes: list[ProposedChange], validation: ValidationResult) -> ChangeProposal:
        proposal_id = str(uuid.uuid4())
        now = _now_iso()
        proposal = ChangeProposal(
            proposal_id=proposal_id,
            bank_name=bank_name,
            instruction=req.instruction,
            target_records=target_records,
            proposed_changes=changes,
            validation=validation,
            status="proposed",
            created_at=now,
            updated_at=now,
        )
        self.save(proposal)
        self._append_history(
            bank_name,
            BankEditHistoryItem(
                proposal_id=proposal_id,
                status="proposed",
                instruction=req.instruction,
                created_at=now,
                updated_at=now,
                validation_status=validation.status,
            ),
        )
        return proposal

    def save(self, proposal: ChangeProposal) -> None:
        p = self._proposal_dir(proposal.bank_name) / f"{proposal.proposal_id}.json"
        p.write_text(json.dumps(proposal.to_json(), indent=2), encoding="utf-8")

    def load(self, *, bank_name: str, proposal_id: str) -> ChangeProposal:
        p = self._proposal_dir(bank_name) / f"{proposal_id}.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        return ChangeProposal.from_json(d)

    def update_status(self, *, bank_name: str, proposal_id: str, status: str, validation_status: str | None = None) -> ChangeProposal:
        proposal = self.load(bank_name=bank_name, proposal_id=proposal_id)
        now = _now_iso()
        updated = ChangeProposal(
            proposal_id=proposal.proposal_id,
            bank_name=proposal.bank_name,
            instruction=proposal.instruction,
            target_records=proposal.target_records,
            proposed_changes=proposal.proposed_changes,
            validation=proposal.validation,
            status=status,
            created_at=proposal.created_at,
            updated_at=now,
        )
        self.save(updated)
        self._update_history(bank_name, proposal_id, status=status, updated_at=now, validation_status=validation_status)
        return updated

    def list_history(self, *, bank_name: str) -> list[BankEditHistoryItem]:
        p = self._history_path(bank_name)
        if not p.exists():
            return []
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return [BankEditHistoryItem.model_validate(x) for x in data]

    def _append_history(self, bank_name: str, item: BankEditHistoryItem) -> None:
        p = self._history_path(bank_name)
        hist = self.list_history(bank_name=bank_name)
        hist.append(item)
        p.write_text(json.dumps([h.model_dump() for h in hist], indent=2), encoding="utf-8")

    def _update_history(self, bank_name: str, proposal_id: str, *, status: str, updated_at: str, validation_status: str | None) -> None:
        hist = self.list_history(bank_name=bank_name)
        out: list[BankEditHistoryItem] = []
        for h in hist:
            if h.proposal_id == proposal_id:
                out.append(
                    BankEditHistoryItem(
                        proposal_id=h.proposal_id,
                        status=status,  # type: ignore[arg-type]
                        instruction=h.instruction,
                        created_at=h.created_at,
                        updated_at=updated_at,
                        validation_status=validation_status or h.validation_status,
                    )
                )
            else:
                out.append(h)
        p = self._history_path(bank_name)
        p.write_text(json.dumps([h.model_dump() for h in out], indent=2), encoding="utf-8")

