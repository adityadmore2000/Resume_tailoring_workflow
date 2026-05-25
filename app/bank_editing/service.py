from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from app.bank_editing.models import (
    BankEditApplyResponse,
    BankEditHistoryResponse,
    BankEditProposeRequest,
    BankEditProposeResponse,
    BankEditRejectResponse,
    ProposedChange,
    ValidationResult,
)
from app.bank_editing.storage import ChangeProposalRepository
from app.bank_editing.validator import extract_evidence_ids, validate_proposed_change
from app.bank_generator.bank_registry import BankRegistry, BankRegistryEntry
from app.bank_generator.folder_manager import BankFolderError, get_bank_paths, safe_join
from app.config import DEFAULT_CONFIG
from app.llm.factory import build_llm_provider
from app.rag.ingest import ingest_experience_bank
from app.rag.retriever import retrieve


def _resolve_record_path(bank_dir: Path, record_id: str) -> Path:
    # Accept `projects/p1.md` style IDs.
    if "/" in record_id or record_id.endswith(".md"):
        return safe_join(bank_dir, record_id)

    # Otherwise, look for a known modular markdown file named `<id>.md`.
    candidates = [
        bank_dir / "work_experience" / f"{record_id}.md",
        bank_dir / "projects" / f"{record_id}.md",
        bank_dir / "capabilities" / f"{record_id}.md",
        bank_dir / "summaries" / f"{record_id}.md",
        bank_dir / "reusable_resume_blocks" / f"{record_id}.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    # Fall back to safe join; will likely fail existence checks downstream.
    return safe_join(bank_dir, f"{record_id}.md")


def propose_bank_edit(*, bank_name: str, req: BankEditProposeRequest) -> BankEditProposeResponse:
    data_root = Path(DEFAULT_CONFIG.data_root)
    try:
        paths = get_bank_paths(data_root, bank_name)
    except BankFolderError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not paths.experience_bank_dir.exists():
        raise HTTPException(status_code=404, detail="Bank not found")

    repo = ChangeProposalRepository(root_dir=data_root)

    target_records: list[dict] = []
    record_path: Path | None = None

    if req.target_record_id:
        record_path = _resolve_record_path(paths.experience_bank_dir, req.target_record_id)
        target_records = [{"record_id": req.target_record_id, "source_file": str(req.target_record_id)}]
    else:
        # Best-effort retrieval via Qdrant to choose a target record.
        try:
            llm = build_llm_provider(DEFAULT_CONFIG)
            hits = retrieve(query=req.instruction, bank_folder_name=paths.bank_folder_name, llm=llm, top_k=6)
            for h in hits:
                target_records.append(
                    {
                        "record_id": str(h.chunk_id),
                        "score": h.score,
                        "source_file": str(h.metadata.get("source_file") or ""),
                        "evidence_ids": list(h.metadata.get("evidence_ids") or []),
                    }
                )
            if hits:
                src = str(hits[0].metadata.get("source_file") or "")
                if src:
                    record_path = safe_join(paths.experience_bank_dir, src)
        except Exception:
            target_records = []
            record_path = None

    if record_path is None or not record_path.exists():
        validation = ValidationResult(status="needs_review", warnings=["No target record found"], unsupported_claims=[], immutable_field_changes=[])
        proposal = repo.create(bank_name=paths.bank_folder_name, req=req, target_records=target_records, changes=[], validation=validation)
        return BankEditProposeResponse(
            proposal_id=proposal.proposal_id,
            bank_name=paths.bank_folder_name,
            target_records=target_records,
            proposed_changes=[],
            validation=validation,
        )

    old_content = record_path.read_text(encoding="utf-8")
    rel_path = str(record_path.relative_to(paths.experience_bank_dir)).replace("\\", "/")
    available_eids = extract_evidence_ids(old_content)
    chosen_eids = [e for e in (req.target_evidence_ids or []) if e in available_eids]
    if not chosen_eids and available_eids:
        chosen_eids = available_eids[:2]

    # Conservative proposal: only rewrite the reusable bullets section.
    # Keep instruction literal; validator will reject risky claims.
    new_bullets = "- (Proposed) " + req.instruction.strip().replace("\n", " ").strip()
    if chosen_eids:
        new_bullets += f" (evidence: {chosen_eids[0]})"
    new_bullets += "\n"

    marker = "## Resume-ready reusable bullets\n"
    start = old_content.find(marker)
    if start < 0:
        validation = ValidationResult(status="failed", immutable_field_changes=["Missing bullets section"], unsupported_claims=[], warnings=[])
        change = ProposedChange(
            record_id=rel_path,
            old_content=old_content,
            new_content=old_content,
            reason="Missing bullets section; cannot propose safe edit.",
            evidence_ids=chosen_eids,
        )
        proposal = repo.create(bank_name=paths.bank_folder_name, req=req, target_records=target_records, changes=[change], validation=validation)
        return BankEditProposeResponse(
            proposal_id=proposal.proposal_id,
            bank_name=paths.bank_folder_name,
            target_records=target_records,
            proposed_changes=[change],
            validation=validation,
        )

    # Replace only the body of the bullets section.
    from app.bank_editing.validator import _split_bullets_section  # local import to keep helper private

    split = _split_bullets_section(old_content)
    assert split is not None
    pre, _old_bullets, post = split
    new_content = pre + "\n" + new_bullets + post

    validation = validate_proposed_change(old_content=old_content, new_content=new_content, evidence_ids=chosen_eids)
    change = ProposedChange(
        record_id=rel_path,
        old_content=old_content,
        new_content=new_content,
        reason="Proposed reusable bullet edit (requires approval).",
        evidence_ids=chosen_eids,
    )

    proposal = repo.create(bank_name=paths.bank_folder_name, req=req, target_records=target_records, changes=[change], validation=validation)
    return BankEditProposeResponse(
        proposal_id=proposal.proposal_id,
        bank_name=paths.bank_folder_name,
        target_records=target_records,
        proposed_changes=[change],
        validation=validation,
    )


def apply_bank_edit(*, bank_name: str, proposal_id: str) -> BankEditApplyResponse:
    data_root = Path(DEFAULT_CONFIG.data_root)
    try:
        paths = get_bank_paths(data_root, bank_name)
    except BankFolderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not paths.experience_bank_dir.exists():
        raise HTTPException(status_code=404, detail="Bank not found")

    repo = ChangeProposalRepository(root_dir=data_root)
    proposal = repo.load(bank_name=paths.bank_folder_name, proposal_id=proposal_id)
    if not proposal.proposed_changes:
        validation = ValidationResult(status="failed", warnings=["No proposed changes"], unsupported_claims=[], immutable_field_changes=[])
        repo.update_status(bank_name=paths.bank_folder_name, proposal_id=proposal_id, status="rejected", validation_status=validation.status)
        return BankEditApplyResponse(proposal_id=proposal_id, bank_name=paths.bank_folder_name, applied=False, validation=validation)

    # Re-validate against current file content before applying.
    final_validation: ValidationResult | None = None
    for ch in proposal.proposed_changes:
        record_path = safe_join(paths.experience_bank_dir, ch.record_id)
        if not record_path.exists():
            final_validation = ValidationResult(
                status="failed",
                warnings=[],
                unsupported_claims=[],
                immutable_field_changes=[f"Record not found: {ch.record_id}"],
            )
            break
        current = record_path.read_text(encoding="utf-8")
        final_validation = validate_proposed_change(old_content=current, new_content=ch.new_content, evidence_ids=ch.evidence_ids)
        if final_validation.status != "passed":
            break

    assert final_validation is not None
    if final_validation.status != "passed":
        repo.update_status(bank_name=paths.bank_folder_name, proposal_id=proposal_id, status="rejected", validation_status=final_validation.status)
        return BankEditApplyResponse(proposal_id=proposal_id, bank_name=paths.bank_folder_name, applied=False, validation=final_validation)

    # Apply changes.
    from app.ui.api.experience_banks_api import write_bank_file

    for ch in proposal.proposed_changes:
        write_bank_file(paths.bank_folder_name, ch.record_id, content=ch.new_content, data_root=data_root)

    # Mark registry as manually modified.
    registry = BankRegistry(data_root / "experience_bank" / "banks_registry.json")
    entries = registry.load()
    existing = next((e for e in entries if e.bank_folder_name == paths.bank_folder_name), None)
    if existing:
        updated = BankRegistryEntry.model_validate(existing.model_dump())
        updated.manually_modified = True  # type: ignore[misc]
        registry.upsert(updated)

    # Best-effort re-index. For now, re-ingest the whole bank.
    try:
        llm = build_llm_provider(DEFAULT_CONFIG)
        ingest_experience_bank(bank_folder_name=paths.bank_folder_name, experience_bank_dir=paths.experience_bank_dir, llm=llm, cfg=DEFAULT_CONFIG)
    except Exception as e:
        final_validation.warnings.append(f"Re-indexing failed: {e}")

    repo.update_status(bank_name=paths.bank_folder_name, proposal_id=proposal_id, status="applied", validation_status=final_validation.status)
    return BankEditApplyResponse(proposal_id=proposal_id, bank_name=paths.bank_folder_name, applied=True, validation=final_validation)


def reject_bank_edit(*, bank_name: str, proposal_id: str) -> BankEditRejectResponse:
    data_root = Path(DEFAULT_CONFIG.data_root)
    try:
        paths = get_bank_paths(data_root, bank_name)
    except BankFolderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not paths.experience_bank_dir.exists():
        raise HTTPException(status_code=404, detail="Bank not found")

    repo = ChangeProposalRepository(root_dir=data_root)
    repo.update_status(bank_name=paths.bank_folder_name, proposal_id=proposal_id, status="rejected", validation_status="rejected")
    return BankEditRejectResponse(proposal_id=proposal_id, bank_name=paths.bank_folder_name, rejected=True)


def list_bank_edit_history(*, bank_name: str) -> BankEditHistoryResponse:
    data_root = Path(DEFAULT_CONFIG.data_root)
    try:
        paths = get_bank_paths(data_root, bank_name)
    except BankFolderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not paths.experience_bank_dir.exists():
        raise HTTPException(status_code=404, detail="Bank not found")

    repo = ChangeProposalRepository(root_dir=data_root)
    hist = repo.list_history(bank_name=paths.bank_folder_name)
    return BankEditHistoryResponse(bank_name=paths.bank_folder_name, history=hist)

