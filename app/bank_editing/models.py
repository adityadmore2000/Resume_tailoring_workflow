from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BankEditProposeRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=4000)
    target_record_id: str | None = None
    target_evidence_ids: list[str] | None = None


class ProposedChange(BaseModel):
    record_id: str
    old_content: str
    new_content: str
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    status: Literal["passed", "failed", "needs_review"]
    unsupported_claims: list[str] = Field(default_factory=list)
    immutable_field_changes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BankEditProposeResponse(BaseModel):
    proposal_id: str
    bank_name: str
    target_records: list[dict] = Field(default_factory=list)
    proposed_changes: list[ProposedChange] = Field(default_factory=list)
    validation: ValidationResult


class BankEditApplyResponse(BaseModel):
    proposal_id: str
    bank_name: str
    applied: bool
    validation: ValidationResult


class BankEditRejectResponse(BaseModel):
    proposal_id: str
    bank_name: str
    rejected: bool


class BankEditHistoryItem(BaseModel):
    proposal_id: str
    status: Literal["proposed", "applied", "rejected"]
    instruction: str
    created_at: str
    updated_at: str
    validation_status: str


class BankEditHistoryResponse(BaseModel):
    bank_name: str
    history: list[BankEditHistoryItem] = Field(default_factory=list)

