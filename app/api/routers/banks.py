from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.bank_generator.bank_builder import generate_experience_bank, list_banks
from app.bank_generator.folder_manager import BankFolderError, get_bank_paths
from app.config import DEFAULT_CONFIG
from app.llm import LLMError
from app.llm.factory import build_llm_provider
from app.ui.api.bank_preview_api import compute_stats
from app.ui.api.experience_banks_api import (
    ExperienceBankAPIError,
    list_bank_files,
    list_bank_items,
    read_bank_file,
)

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
    vector_chunks: int = 0
    evidence_claims: int = 0
    messages: list[str] = Field(default_factory=list)


@router.post("")
async def api_create_bank(
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

    try:
        cfg = DEFAULT_CONFIG
        llm = build_llm_provider(cfg)
        res = generate_experience_bank(
            resume_tex=resume_text or "",
            bank_folder_name=bank_name,
            llm=llm,
            overwrite=overwrite,
            source_format=source_format,
        )
        if not res.validation.ok:
            raise HTTPException(status_code=400, detail={"errors": res.validation.errors, "warnings": res.validation.warnings})
        return CreateBankResponse(
            bank_folder_name=res.bank_folder_name,
            vector_chunks=res.vector_records,
            evidence_claims=len(res.index.evidence_claims) if res.index else 0,
            messages=res.messages or [],
        )
    except BankFolderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LLMError as e:
        raise HTTPException(status_code=400, detail=f"Model output malformed during bank generation: {e}")


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
