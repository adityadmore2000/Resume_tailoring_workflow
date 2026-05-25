from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.bank_generator.bank_builder import generate_experience_bank, list_banks
from app.bank_generator.bank_registry import BankRegistry, BankRegistryEntry
from app.bank_generator.folder_manager import BankFolderError, get_bank_paths
from app.config import DEFAULT_CONFIG
from app.llm import LLMError
from app.llm.factory import build_llm_provider
from app.rag.ingest import ingest_experience_bank
from app.ui.api.bank_preview_api import compute_stats
from app.ui.api.experience_banks_api import (
    ExperienceBankAPIError,
    list_bank_files,
    list_bank_items,
    read_bank_file,
    write_bank_file,
)
from app.tasks.task_progress import TASKS

router = APIRouter(prefix="/api/banks", tags=["banks"])


class BankListItem(BaseModel):
    bank_folder_name: str
    status: str | None = None
    source_format: str | None = None
    updated_at: str | None = None


@router.get("")
def api_list_banks() -> dict:
    banks = list_banks()
    return {"banks": [BankListItem(**b.model_dump()).model_dump() for b in banks]}


class CreateBankResponse(BaseModel):
    bank_folder_name: str
    task_id: str
    status: str = "running"
    vector_chunks: int = 0
    evidence_claims: int = 0
    messages: list[str] = Field(default_factory=list)


@router.post("")
async def api_create_bank(
    background_tasks: BackgroundTasks,
    bank_name: str = Form(...),
    overwrite: bool = Form(False),
    source_format: str = Form("latex"),
    file: UploadFile | None = None,
    resume_text: str | None = Form(None),
) -> CreateBankResponse:
    """
    Create an Experience Bank from an uploaded master resume.
    Next.js should send either:
    - multipart with `file`, or
    - form field `resume_text`
    """
    if not bank_name.strip():
        raise HTTPException(status_code=400, detail="bank_name is required")
    if file is None and not (resume_text or "").strip():
        raise HTTPException(status_code=400, detail="Provide either file or resume_text")

    if file is not None:
        if file.filename and file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="PDF parsing not supported yet (upload .tex or .txt).")
        raw = await file.read()
        resume_text = raw.decode("utf-8", errors="replace")
        if file.filename and file.filename.lower().endswith(".txt"):
            source_format = "text"
        else:
            source_format = "latex"

    cfg = DEFAULT_CONFIG

    progress = TASKS.create(
        task_type="experience_bank_generation",
        steps=[
            ("resume_parsed", "Resume Parsed"),
            ("experience_extracted", "Experience Extracted"),
            ("knowledge_structured", "Knowledge Structured"),
            ("bank_generated", "Bank Generated"),
            ("saved", "Saved"),
        ],
    )

    def _run() -> None:
        try:
            llm = build_llm_provider(cfg)
            res = generate_experience_bank(
                resume_tex=resume_text or "",
                bank_folder_name=bank_name,
                llm=llm,
                overwrite=overwrite,
                source_format=source_format,
                task_id=progress.task_id,
            )
            if not res.validation.ok:
                TASKS.fail(task_id=progress.task_id, step_id=progress.current_step, error="Bank validation failed")
                TASKS.set_result(
                    task_id=progress.task_id,
                    result={"errors": res.validation.errors, "warnings": res.validation.warnings, "messages": res.messages},
                )
                return
        except (BankFolderError, LLMError, Exception) as e:
            TASKS.fail(task_id=progress.task_id, step_id=progress.current_step, error=str(e))

    background_tasks.add_task(_run)
    return CreateBankResponse(bank_folder_name=bank_name, task_id=progress.task_id, status="running", messages=[])


@router.get("/{bank_name}")
def api_get_bank(bank_name: str) -> dict:
    banks = list_banks()
    b = next((x for x in banks if x.bank_folder_name == bank_name), None)
    if not b:
        raise HTTPException(status_code=404, detail="Bank not found")
    return {"bank": b.model_dump()}


@router.get("/{bank_name}/files")
def api_list_bank_files(bank_name: str) -> dict:
    try:
        files = list_bank_files(bank_name)
        return {"files": [asdict(f) for f in files]}
    except ExperienceBankAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{bank_name}/files/content")
def api_read_bank_file(bank_name: str, path: str) -> dict:
    try:
        rel, title, content = read_bank_file(bank_name, path)
        return {"path": rel, "title": title, "content": content}
    except ExperienceBankAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{bank_name}/items")
def api_list_bank_items(bank_name: str) -> dict:
    """
    Human-readable summaries (Experience / Projects / Capabilities) for the preview UI.
    """
    try:
        items = list_bank_items(bank_name)
        return {"items": [asdict(x) for x in items]}
    except ExperienceBankAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{bank_name}/stats")
def api_bank_stats(bank_name: str) -> dict:
    try:
        data_root = Path(DEFAULT_CONFIG.data_root)
        paths = get_bank_paths(data_root, bank_name)
        if not paths.experience_bank_dir.exists():
            raise HTTPException(status_code=404, detail="Bank not found")
        s = compute_stats(paths.experience_bank_dir, paths.vector_store_dir, paths.bank_folder_name)
        return {"stats": asdict(s)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class UpdateBankMetadataRequest(BaseModel):
    display_name: str | None = None
    notes: str | None = None


@router.put("/{bank_name}/metadata")
def api_update_bank_metadata(bank_name: str, body: UpdateBankMetadataRequest) -> dict:
    data_root = Path(DEFAULT_CONFIG.data_root)
    paths = get_bank_paths(data_root, bank_name)
    if not paths.experience_bank_dir.exists():
        raise HTTPException(status_code=404, detail="Bank not found")

    registry = BankRegistry(data_root / "experience_bank" / "banks_registry.json")
    entries = registry.load()
    existing = next((e for e in entries if e.bank_folder_name == paths.bank_folder_name), None)
    if not existing:
        raise HTTPException(status_code=404, detail="Bank not registered")

    updated = BankRegistryEntry.model_validate(existing.model_dump())
    if body.display_name is not None:
        updated.display_name = body.display_name  # type: ignore[misc]
    if body.notes is not None:
        updated.notes = body.notes  # type: ignore[misc]
    registry.upsert(updated)
    return {"bank": updated.model_dump()}


class PutBankFileRequest(BaseModel):
    path: str
    content: str


@router.put("/{bank_name}/files/content")
def api_put_bank_file_content(bank_name: str, body: PutBankFileRequest) -> dict:
    data_root = Path(DEFAULT_CONFIG.data_root)
    paths = get_bank_paths(data_root, bank_name)
    if not paths.experience_bank_dir.exists():
        raise HTTPException(status_code=404, detail="Bank not found")
    try:
        rel = write_bank_file(paths.bank_folder_name, body.path, content=body.content, data_root=data_root)
    except ExperienceBankAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Mark registry as manually modified.
    registry = BankRegistry(data_root / "experience_bank" / "banks_registry.json")
    entries = registry.load()
    existing = next((e for e in entries if e.bank_folder_name == paths.bank_folder_name), None)
    if existing:
        updated = BankRegistryEntry.model_validate(existing.model_dump())
        updated.manually_modified = True  # type: ignore[misc]
        registry.upsert(updated)
    return {"path": rel, "ok": True}


@router.post("/{bank_name}/reingest")
def api_reingest_bank(bank_name: str, background_tasks: BackgroundTasks) -> dict:
    data_root = Path(DEFAULT_CONFIG.data_root)
    paths = get_bank_paths(data_root, bank_name)
    if not paths.experience_bank_dir.exists():
        raise HTTPException(status_code=404, detail="Bank not found")

    cfg = DEFAULT_CONFIG
    progress = TASKS.create(
        task_type="experience_bank_generation",
        steps=[
            ("resume_parsed", "Resume Parsed"),
            ("experience_extracted", "Experience Extracted"),
            ("knowledge_structured", "Knowledge Structured"),
            ("bank_generated", "Bank Generated"),
            ("saved", "Saved"),
        ],
    )

    def _run() -> None:
        try:
            llm = build_llm_provider(cfg)
            # Fast-forward the first three steps (re-ingestion doesn't redo parsing/extraction).
            TASKS.advance(task_id=progress.task_id, step_id="resume_parsed")
            TASKS.advance(task_id=progress.task_id, step_id="experience_extracted")
            TASKS.advance(task_id=progress.task_id, step_id="knowledge_structured")
            ingest_experience_bank(bank_folder_name=paths.bank_folder_name, experience_bank_dir=paths.experience_bank_dir, llm=llm, cfg=cfg)
            TASKS.advance(task_id=progress.task_id, step_id="bank_generated")

            registry = BankRegistry(data_root / "experience_bank" / "banks_registry.json")
            entries = registry.load()
            existing = next((e for e in entries if e.bank_folder_name == paths.bank_folder_name), None)
            if existing:
                updated = BankRegistryEntry.model_validate(existing.model_dump())
                registry.upsert(updated)
            TASKS.advance(task_id=progress.task_id, step_id="saved")
            TASKS.set_result(task_id=progress.task_id, result={"bank_folder_name": paths.bank_folder_name})
            TASKS.complete(task_id=progress.task_id)
        except Exception as e:
            TASKS.fail(task_id=progress.task_id, step_id=progress.current_step, error=str(e))

    background_tasks.add_task(_run)
    return {"task_id": progress.task_id, "status": "running", "bank_folder_name": paths.bank_folder_name}
