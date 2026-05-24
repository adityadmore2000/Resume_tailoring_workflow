from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BankRegistryEntry(BaseModel):
    bank_folder_name: str
    original_resume_path: str
    experience_bank_path: str
    vector_store_path: str
    source_format: str = "latex"
    status: str = "generated"
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)
    notes: str = ""


@dataclass(frozen=True)
class BankRegistry:
    registry_path: Path

    def load(self) -> list[BankRegistryEntry]:
        if not self.registry_path.exists():
            return []
        data = json.loads(self.registry_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        out: list[BankRegistryEntry] = []
        for item in data:
            if isinstance(item, dict):
                out.append(BankRegistryEntry.model_validate(item))
        return out

    def upsert(self, entry: BankRegistryEntry) -> None:
        entries = self.load()
        by_name = {e.bank_folder_name: e for e in entries}
        if entry.bank_folder_name in by_name:
            existing = by_name[entry.bank_folder_name]
            entry.created_at = existing.created_at  # type: ignore[misc]
            entry.updated_at = _now_iso()  # type: ignore[misc]
        by_name[entry.bank_folder_name] = entry
        new_list = [e.model_dump() for e in by_name.values()]
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(json.dumps(new_list, indent=2), encoding="utf-8")

