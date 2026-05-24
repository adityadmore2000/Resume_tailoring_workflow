from __future__ import annotations

from dataclasses import dataclass

from app.bank_generator.schemas import ExperienceBankIndex


@dataclass(frozen=True)
class BankValidationResult:
    ok: bool
    errors: list[str]
    warnings: list[str]


def validate_experience_bank(index: ExperienceBankIndex) -> BankValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    ev_ids = {e.evidence_id for e in index.evidence_claims}
    if not ev_ids:
        warnings.append("No evidence claims extracted; bank will be mostly empty.")

    for e in index.evidence_claims:
        if not e.source_text.strip():
            errors.append(f"Evidence {e.evidence_id} missing source_text.")
        if not e.source_section.strip():
            errors.append(f"Evidence {e.evidence_id} missing source_section.")

    for m in index.metrics:
        if m.evidence_id not in ev_ids:
            errors.append(f"Metric {m.metric_id} references unknown evidence_id {m.evidence_id}.")

    for b in index.reusable_bullets:
        if not b.evidence_ids:
            errors.append(f"Reusable bullet {b.bullet_id} has no evidence_ids (blocked).")
        for eid in b.evidence_ids:
            if eid not in ev_ids:
                errors.append(f"Reusable bullet {b.bullet_id} references unknown evidence_id {eid}.")

    ok = len(errors) == 0
    return BankValidationResult(ok=ok, errors=errors, warnings=warnings)

