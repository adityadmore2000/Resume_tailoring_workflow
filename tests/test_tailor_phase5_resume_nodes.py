from __future__ import annotations

import inspect
import json

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import select

import app.api.routers.tailor as tailor_mod
import app.api.routers.banks as banks_mod
import app.api.routers.retrieve_debug as retrieve_debug_mod
import app.api.services.tailor_service as tailor_service_mod
from app.banks_pg.service import slugify_bank_name, BanksService
from app.db.models import Resume
from app.generated_resumes.resume_store import get_generated_resume_paths, read_traceability
from app.schemas import JDAnalysis
from app.rewriter import BulletRewriteOut
from app.tasks.task_progress import TASKS


class DummyLLM:
    def __init__(self, dim: int = 8):
        self._dim = dim

    def embed_text(self, text: str) -> list[float]:
        # Tiny deterministic embedding; Qdrant in-memory is fine with constant vectors.
        return [0.1] * self._dim

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]

    def generate_text(self, *, system: str, user: str) -> str:
        return "{}"

    def generate_json(self, *, system: str, user: str, schema, max_retries: int = 1, allow_fallback: bool = True):
        if schema is JDAnalysis:
            return JDAnalysis(required_skills=["python"], preferred_skills=[], role_focus=["backend"], important_keywords=["fastapi"])
        if schema is BulletRewriteOut:
            # Keep original bullet content unchanged (deterministic + verifier-safe).
            # The rewrite prompt embeds the original bullet in JSON, so we can simply return a generic.
            return BulletRewriteOut(suggested_latex="Improved bullet.", rationale="deterministic stub")
        # Fallback: instantiate with defaults if possible.
        return schema.model_validate({})


async def _run_background_tasks(bg: BackgroundTasks) -> None:
    for t in list(bg.tasks):
        res = t.func(*t.args, **t.kwargs)
        if inspect.isawaitable(res):
            await res


@pytest.mark.asyncio
async def test_tailor_uses_resume_nodes_and_does_not_hit_not_migrated_guard(db_session, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QDRANT_URL", ":memory:")

    # Patch LLM provider in the exact modules that import it.
    monkeypatch.setattr(tailor_service_mod, "build_llm_provider", lambda cfg: DummyLLM(dim=8))
    monkeypatch.setattr(retrieve_debug_mod, "build_llm_provider", lambda cfg: DummyLLM(dim=8))

    # Create bank in Postgres (resume + resume_nodes).
    bg = BackgroundTasks()
    _ = await banks_mod.api_create_bank(
        background_tasks=bg,
        bank_name="My Bank",
        overwrite=False,
        source_format="latex",
        file=None,
        resume_text="\\section{Experience}\\begin{itemize}\\item Built X in Python\\end{itemize}",
    )
    await _run_background_tasks(bg)

    slug = slugify_bank_name("My Bank")
    resume = (await db_session.execute(select(Resume).where(Resume.slug == slug))).scalar_one()

    # Tailor via the active runtime router (but run background tasks inline).
    bg2 = BackgroundTasks()
    resp = await tailor_mod.api_tailor(
        body=tailor_mod.TailorRequest(bank_name="My Bank", jd_text="Python backend FastAPI"),
        background_tasks=bg2,
        session=db_session,
    )
    assert resp.bank_folder_name == slug
    assert resp.status == "running"
    assert resp.task_id

    await _run_background_tasks(bg2)

    prog = TASKS.get(resp.task_id)
    assert prog is not None
    assert prog.status == "completed"
    assert prog.error is None
    assert prog.result is not None
    assert "not yet migrated" not in json.dumps(prog.result).casefold()

    # Ensure task steps advanced past JD analysis + matching.
    step_by_id = {s["id"]: s for s in prog.to_dict()["steps"]}
    assert step_by_id["jd_analyzed"]["status"] == "completed"
    assert step_by_id["experience_matched"]["status"] == "completed"

    # Ensure the generated resume traceability links back to the Postgres resume_id and has non-empty context.
    gen_resume_id = prog.result.get("resume_id")
    assert isinstance(gen_resume_id, str) and gen_resume_id
    paths = get_generated_resume_paths(bank_folder_name=slug, resume_id=gen_resume_id)
    trace = read_traceability(paths)
    assert isinstance(trace, dict)
    assert trace.get("resume_id") == str(resume.id)
    ctx = trace.get("context") or {}
    assert isinstance(ctx, dict)
    assert (ctx.get("sections") or []) != []


@pytest.mark.asyncio
async def test_retrieve_nodes_debug_indexes_and_returns_non_empty_context(db_session, monkeypatch):
    monkeypatch.setenv("QDRANT_URL", ":memory:")
    monkeypatch.setattr(retrieve_debug_mod, "build_llm_provider", lambda cfg: DummyLLM(dim=8))

    res = await BanksService(db_session).create_bank_from_resume_text(
        bank_name="Dbg Bank",
        resume_text="\\section{Projects}\\begin{itemize}\\item Shipped API\\end{itemize}",
        source_format="latex",
        overwrite=False,
    )

    out = await retrieve_debug_mod.api_retrieve_nodes_debug(
        resume_id=str(res.resume_id),
        body=retrieve_debug_mod.RetrieveNodesDebugRequest(jd_text="api backend", top_k=5),
        session=db_session,
    )
    assert out["resume_id"] == str(res.resume_id)
    assert out["context"]["sections"], "Expected non-empty context when searchable nodes exist"

