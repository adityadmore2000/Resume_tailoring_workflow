from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.api.services.tailor_service import TailorError, tailor_resume_from_bank
from app.tasks.task_progress import TASKS

router = APIRouter(prefix="/api", tags=["tailor"])


class TailorRequest(BaseModel):
    bank_name: str = Field(min_length=1)
    jd_text: str = Field(min_length=1)


class TailorResponse(BaseModel):
    bank_folder_name: str
    task_id: str
    status: str = "running"


@router.post("/tailor", response_model=TailorResponse)
def api_tailor(body: TailorRequest, background_tasks: BackgroundTasks):
    try:
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
                tailor_resume_from_bank(bank_folder_name=body.bank_name, jd_text=body.jd_text, task_id=progress.task_id)
            except Exception as e:
                TASKS.fail(task_id=progress.task_id, step_id=progress.current_step, error=str(e))

        background_tasks.add_task(_run)
        return TailorResponse(bank_folder_name=body.bank_name, task_id=progress.task_id, status="running")
    except TailorError as e:
        raise HTTPException(status_code=400, detail=str(e))
