from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
import uuid
from typing import Literal


TaskType = Literal["experience_bank_generation", "resume_tailoring"]
TaskStatus = Literal["running", "completed", "failed"]
StepStatus = Literal["pending", "active", "completed", "failed"]


@dataclass(frozen=True)
class TaskStep:
    id: str
    label: str
    status: StepStatus = "pending"


@dataclass
class TaskProgress:
    task_id: str
    task_type: TaskType
    status: TaskStatus = "running"
    current_step: str | None = None
    steps: list[TaskStep] = field(default_factory=list)
    error: str | None = None
    result: dict | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status,
            "current_step": self.current_step,
            "steps": [s.__dict__ for s in self.steps],
            "error": self.error,
            "result": self.result,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class TaskProgressStore:
    """
    In-memory task progress store (non-persistent).
    Suitable for a single-process dev server; can be replaced with Redis/DB later.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, TaskProgress] = {}

    def create(self, *, task_type: TaskType, steps: list[tuple[str, str]]) -> TaskProgress:
        task_id = uuid.uuid4().hex
        prog = TaskProgress(
            task_id=task_id,
            task_type=task_type,
            status="running",
            current_step=steps[0][0] if steps else None,
            steps=[TaskStep(id=sid, label=label) for sid, label in steps],
        )
        if prog.steps:
            prog.steps[0] = TaskStep(id=prog.steps[0].id, label=prog.steps[0].label, status="active")
        with self._lock:
            self._tasks[task_id] = prog
        return prog

    def get(self, task_id: str) -> TaskProgress | None:
        with self._lock:
            return self._tasks.get(task_id)

    def _touch(self, p: TaskProgress) -> None:
        p.updated_at = datetime.now(timezone.utc).isoformat()

    def set_step(self, *, task_id: str, step_id: str, status: StepStatus) -> None:
        with self._lock:
            p = self._tasks.get(task_id)
            if not p:
                return
            new_steps: list[TaskStep] = []
            for s in p.steps:
                if s.id == step_id:
                    new_steps.append(TaskStep(id=s.id, label=s.label, status=status))
                else:
                    new_steps.append(s)
            p.steps = new_steps
            p.current_step = step_id
            self._touch(p)

    def advance(self, *, task_id: str, step_id: str) -> None:
        with self._lock:
            p = self._tasks.get(task_id)
            if not p:
                return
            steps = list(p.steps)
            idx = next((i for i, s in enumerate(steps) if s.id == step_id), None)
            if idx is None:
                return
            # Mark previous as completed
            steps[idx] = TaskStep(id=steps[idx].id, label=steps[idx].label, status="completed")
            # Activate next
            if idx + 1 < len(steps):
                steps[idx + 1] = TaskStep(id=steps[idx + 1].id, label=steps[idx + 1].label, status="active")
                p.current_step = steps[idx + 1].id
            else:
                p.current_step = step_id
            p.steps = steps
            self._touch(p)

    def fail(self, *, task_id: str, step_id: str | None, error: str) -> None:
        with self._lock:
            p = self._tasks.get(task_id)
            if not p:
                return
            p.status = "failed"
            p.error = error
            if step_id:
                p.current_step = step_id
                p.steps = [TaskStep(id=s.id, label=s.label, status=("failed" if s.id == step_id else s.status)) for s in p.steps]
            self._touch(p)

    def complete(self, *, task_id: str) -> None:
        with self._lock:
            p = self._tasks.get(task_id)
            if not p:
                return
            p.status = "completed"
            p.current_step = p.current_step or (p.steps[-1].id if p.steps else None)
            p.steps = [TaskStep(id=s.id, label=s.label, status="completed") for s in p.steps]
            self._touch(p)

    def set_result(self, *, task_id: str, result: dict) -> None:
        with self._lock:
            p = self._tasks.get(task_id)
            if not p:
                return
            p.result = result
            self._touch(p)


TASKS = TaskProgressStore()
