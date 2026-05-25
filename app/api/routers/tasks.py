from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.tasks.task_progress import TASKS

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskProgressResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    current_step: str | None = None
    steps: list[dict]
    error: str | None = None
    result: dict | None = None
    created_at: str
    updated_at: str


@router.get("/{task_id}/progress", response_model=TaskProgressResponse)
def api_get_task_progress(task_id: str):
    p = TASKS.get(task_id)
    if not p:
        raise HTTPException(status_code=404, detail="Task not found")
    return p.to_dict()
