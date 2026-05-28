from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.services.tailor_service import TailorError, tailor_resume_from_bank
import uuid

from app.banks_pg.service import BanksService, slugify_bank_name
from app.db.deps import get_db_session
from app.db.models import Resume
from app.tasks.task_progress import TASKS
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api", tags=["tailor"])


class TailorRequest(BaseModel):
    bank_name: str = Field(min_length=1)
    jd_text: str = Field(min_length=1)


class TailorResponse(BaseModel):
    bank_folder_name: str
    task_id: str
    status: str = "running"


@router.post("/tailor", response_model=TailorResponse)
async def api_tailor(
    body: TailorRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
):
    try:
        # Phase 4: Experience Banks are backed by Postgres `resumes`/`resume_nodes`.
        # Tailor must resolve the selected bank through Postgres, not local disk folders.
        selected_bank = body.bank_name

        bsvc = BanksService(session)
        lookup_mode = "slug"
        slug = slugify_bank_name(selected_bank)
        resume = await bsvc.get_resume_by_slug(slug)
        try:
            rid = uuid.UUID(selected_bank)
        except Exception:
            rid = None
        if resume is None and rid is not None:
            lookup_mode = "id"
            resume = (await session.execute(select(Resume).where(Resume.id == rid))).scalar_one_or_none()
            if resume is not None:
                slug = resume.slug
        if resume is None:
            resumes = await bsvc.list_resumes()
            available = [r.slug for r in resumes][:50]
            raise HTTPException(
                status_code=404,
                detail={
                    "detail": "Resume not found for selected bank",
                    "selected_bank": selected_bank,
                    "lookup_mode": lookup_mode,
                    "available_banks": available,
                },
            )

        progress = TASKS.create(
            task_type="resume_tailoring",
            steps=[
                ("resume_parsed", "Resume Parsed"),
                ("jd_analyzed", "JD Analyzed"),
                ("experience_matched", "Experience Matched"),
                ("content_tailored", "Content Tailored"),
                ("finalized", "Finalized"),
            ],
        )

        def _run() -> None:
            try:
                tailor_resume_from_bank(bank_folder_name=slug, jd_text=body.jd_text, task_id=progress.task_id)
            except Exception as e:
                TASKS.fail(task_id=progress.task_id, step_id=progress.current_step, error=str(e))

        background_tasks.add_task(_run)
        return TailorResponse(bank_folder_name=slug, task_id=progress.task_id, status="running")
    except TailorError as e:
        raise HTTPException(status_code=400, detail=str(e))
