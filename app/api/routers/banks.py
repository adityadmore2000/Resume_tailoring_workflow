from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.banks_pg.service import BanksService, slugify_bank_name
from app.db.deps import get_db_session
from app.db.session import get_sessionmaker
from app.db.models import ResumeNode
from app.resume_tree.service import ResumeTreeService
from app.resume_tree.hierarchy_inference import infer_nodes
from app.tasks.task_progress import TASKS

router = APIRouter(prefix="/api/banks", tags=["banks"])


class BankListItem(BaseModel):
    bank_folder_name: str
    status: str | None = None
    source_format: str | None = None
    updated_at: str | None = None


@router.get("")
async def api_list_banks(session: AsyncSession = Depends(get_db_session)) -> dict:
    svc = BanksService(session)
    resumes = await svc.list_resumes()
    out: list[dict] = []
    for r in resumes:
        out.append(
            BankListItem(
                bank_folder_name=r.slug,
                status="ready",
                source_format=(r.metadata_ or {}).get("source_format"),
                updated_at=r.updated_at.isoformat(),
            ).model_dump()
        )
    return {"banks": out}


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
    if not bank_name.strip():
        raise HTTPException(status_code=400, detail="bank_name is required")
    if file is None and not (resume_text or "").strip():
        raise HTTPException(status_code=400, detail="Provide either file or resume_text")

    if file is not None:
        raw = await file.read()
        resume_text = raw.decode("utf-8", errors="replace")
        if file.filename and file.filename.lower().endswith(".txt"):
            source_format = "text"
        else:
            source_format = "latex"

    progress = TASKS.create(
        task_type="experience_bank_generation",
        steps=[
            ("resume_parsed", "Resume Parsed"),
            ("tree_created", "Resume Tree Created"),
            ("saved", "Saved"),
        ],
    )

    slug = slugify_bank_name(bank_name)

    sessionmaker = get_sessionmaker()

    async def _run_async() -> None:
        try:
            TASKS.advance(task_id=progress.task_id, step_id="resume_parsed")
            async with sessionmaker() as session:
                svc = BanksService(session)
                res = await svc.create_bank_from_resume_text(
                    bank_name=bank_name,
                    resume_text=resume_text or "",
                    source_format=source_format,
                    overwrite=overwrite,
                )
            TASKS.advance(task_id=progress.task_id, step_id="tree_created")
            TASKS.set_result(task_id=progress.task_id, result={"bank_folder_name": res.slug, "resume_id": str(res.resume_id)})
            TASKS.advance(task_id=progress.task_id, step_id="saved")
            TASKS.complete(task_id=progress.task_id)
        except Exception as e:
            TASKS.fail(task_id=progress.task_id, step_id=progress.current_step, error=str(e))

    # Run in background to preserve existing "task progress" UI contract.
    background_tasks.add_task(_run_async)
    return CreateBankResponse(bank_folder_name=slug, task_id=progress.task_id, status="running", messages=[])


@router.get("/{bank_name}")
async def api_get_bank(bank_name: str, session: AsyncSession = Depends(get_db_session)) -> dict:
    slug = slugify_bank_name(bank_name)
    svc = BanksService(session)
    r = await svc.get_resume_by_slug(slug)
    if not r:
        raise HTTPException(status_code=404, detail="Bank not found")
    return {
        "bank": {
            "bank_folder_name": r.slug,
            "status": "ready",
            "source_format": (r.metadata_ or {}).get("source_format"),
            "updated_at": r.updated_at.isoformat(),
        }
    }


@router.get("/{bank_name}/tree")
async def api_get_bank_tree(bank_name: str, session: AsyncSession = Depends(get_db_session)) -> dict:
    slug = slugify_bank_name(bank_name)
    bsvc = BanksService(session)
    r = await bsvc.get_resume_by_slug(slug)
    if not r:
        raise HTTPException(status_code=404, detail="Bank not found")
    tsvc = ResumeTreeService(session)
    return await tsvc.retrieve_full_resume_tree(r.id)


class BankItemSummary(BaseModel):
    id: str
    type: str
    title: str
    raw_path: str = ""
    domains: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    date_range: str = ""
    location: str = ""


def _map_section_to_item_type(section_name: str) -> str:
    t = (section_name or "").strip().casefold()
    if "experience" in t or "work" in t:
        return "work_experience"
    if "project" in t:
        return "project"
    if "summary" in t:
        return "summary"
    if "skill" in t:
        return "capability"
    return "capability"


@router.get("/{bank_name}/items")
async def api_list_bank_items(bank_name: str, session: AsyncSession = Depends(get_db_session)) -> dict:
    slug = slugify_bank_name(bank_name)
    bsvc = BanksService(session)
    r = await bsvc.get_resume_by_slug(slug)
    if not r:
        raise HTTPException(status_code=404, detail="Bank not found")

    nodes = (
        await session.execute(
            select(ResumeNode)
            .where(ResumeNode.resume_id == r.id)
            .order_by(ResumeNode.parent_id.nullsfirst(), ResumeNode.order_index, ResumeNode.created_at)
        )
    ).scalars().all()
    inferred = infer_nodes(nodes)

    items: list[dict] = []
    for n in nodes:
        view = inferred.get(n.id)
        if view is None or not view.searchable:
            continue
        sec_name = view.section_label

        md = n.metadata_ or {}
        tools = md.get("tools") if isinstance(md, dict) else None

        title = n.title or ""
        if not title and isinstance(n.content, dict):
            title = str(n.content.get("plain") or n.content.get("text") or n.content.get("latex") or "")
        title = (title or "").strip() or "Untitled"

        items.append(
            BankItemSummary(
                id=str(n.id),
                type=_map_section_to_item_type(sec_name) if sec_name else "capability",
                title=title,
                tools=[str(t).strip() for t in (tools or []) if str(t).strip()] if isinstance(tools, list) else [],
            ).model_dump()
        )

    return {"items": items}


# Legacy endpoints are intentionally disabled in Postgres source-of-truth mode.
@router.get("/{bank_name}/files")
def api_list_bank_files(bank_name: str) -> dict:
    raise HTTPException(status_code=501, detail="Bank files API is disabled (Postgres is runtime source-of-truth).")


@router.delete("/{bank_name}")
def api_delete_bank(bank_name: str) -> dict:
    raise HTTPException(status_code=501, detail="Bank delete API is disabled (Postgres is runtime source-of-truth).")
