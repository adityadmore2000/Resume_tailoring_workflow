from __future__ import annotations

from app.api.routers.tasks import api_get_task_progress
from app.tasks.task_progress import TASKS


def test_task_progress_lifecycle():
    p = TASKS.create(
        task_type="resume_tailoring",
        steps=[
            ("resume_parsed", "Resume Parsed"),
            ("jd_analyzed", "JD Analyzed"),
        ],
    )
    assert p.status == "running"
    assert p.steps[0].status == "active"

    TASKS.advance(task_id=p.task_id, step_id="resume_parsed")
    got = TASKS.get(p.task_id)
    assert got is not None
    assert got.steps[0].status == "completed"
    assert got.steps[1].status == "active"

    TASKS.fail(task_id=p.task_id, step_id="jd_analyzed", error="boom")
    got2 = TASKS.get(p.task_id)
    assert got2 is not None
    assert got2.status == "failed"
    assert got2.error == "boom"


def test_tasks_progress_handler_returns_shape():
    p = TASKS.create(task_type="experience_bank_generation", steps=[("resume_parsed", "Resume Parsed")])
    data = api_get_task_progress(p.task_id)
    assert data["task_id"] == p.task_id
    assert "steps" in data and isinstance(data["steps"], list)

