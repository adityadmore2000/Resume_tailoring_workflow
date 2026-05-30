from __future__ import annotations

import builtins
import importlib
import inspect
from pathlib import Path

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import select

import app.api.routers.banks as banks_mod
import app.api.services.tailor_service as tailor_service_mod
from app.banks_pg.service import BanksService, slugify_bank_name
from app.db.models import Resume
from app.schemas import JDAnalysis
from app.rewriter import BulletRewriteOut


class DummyLLM:
    def __init__(self, dim: int = 8):
        self._dim = dim

    def embed_text(self, text: str) -> list[float]:
        return [0.1] * self._dim

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]

    def generate_text(self, *, system: str, user: str) -> str:
        return "{}"

    def generate_json(self, *, system: str, user: str, schema, max_retries: int = 1, allow_fallback: bool = True):
        if schema is JDAnalysis:
            return JDAnalysis(required_skills=["python"], preferred_skills=[], role_focus=["backend"], important_keywords=["fastapi"])
        if schema is BulletRewriteOut:
            return BulletRewriteOut(suggested_latex="Improved bullet.", rationale="deterministic stub")
        return schema.model_validate({})


async def _run_background_tasks(bg: BackgroundTasks) -> None:
    for t in list(bg.tasks):
        res = t.func(*t.args, **t.kwargs)
        if inspect.isawaitable(res):
            await res


def _block_legacy_imports(monkeypatch: pytest.MonkeyPatch, *, prefixes: tuple[str, ...]) -> None:
    real_import = builtins.__import__

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        if any(name == p or name.startswith(p + ".") for p in prefixes):
            raise AssertionError(f"Legacy import attempted: {name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded)


def _block_legacy_file_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    real_open = builtins.open

    def guarded(file, *args, **kwargs):
        p = str(file)
        if p.endswith("banks_registry.json") or p.endswith("experience_bank_index.json"):
            raise AssertionError(f"Legacy runtime file dependency attempted: {p}")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded)


def test_app_import_does_not_require_streamlit(monkeypatch):
    _block_legacy_imports(monkeypatch, prefixes=("streamlit",))
    import app.main as main_mod

    importlib.reload(main_mod)
    assert callable(main_mod.create_app)


def test_tailor_router_uses_async_entrypoint_and_no_asyncio_run():
    import app.api.routers.tailor as tailor_router_mod

    src = inspect.getsource(tailor_router_mod.api_tailor)
    assert "tailor_resume_from_bank_async" in src
    assert "tailor_resume_from_bank(" not in src
    assert "asyncio.run" not in src


@pytest.mark.asyncio
async def test_runtime_works_without_data_experience_bank(db_session, tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QDRANT_URL", ":memory:")

    # Explicitly simulate deletion of legacy folders/files.
    legacy_dir = tmp_path / "data" / "experience_bank"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    (legacy_dir / "banks_registry.json").write_text("{}", encoding="utf-8")
    (legacy_dir / "metadata").mkdir(parents=True, exist_ok=True)
    (legacy_dir / "metadata" / "experience_bank_index.json").write_text("{}", encoding="utf-8")
    # Delete them: runtime must still work.
    for p in [legacy_dir / "banks_registry.json", legacy_dir / "metadata" / "experience_bank_index.json"]:
        p.unlink()
    (legacy_dir / "metadata").rmdir()
    legacy_dir.rmdir()

    _block_legacy_imports(monkeypatch, prefixes=("app.rag", "app.bank_generator", "app.bank_editing", "app.ui"))
    _block_legacy_file_reads(monkeypatch)

    bg = BackgroundTasks()
    _ = await banks_mod.api_create_bank(
        background_tasks=bg,
        bank_name="No Legacy Files",
        overwrite=False,
        source_format="latex",
        file=None,
        resume_text="\\section{Experience}\\begin{itemize}\\item Built X\\end{itemize}",
    )
    await _run_background_tasks(bg)

    data = await banks_mod.api_list_banks(session=db_session)
    assert any(b["bank_folder_name"] == slugify_bank_name("No Legacy Files") for b in data["banks"])

    # Ensure tailoring path does not import or read any legacy file-bank modules.
    monkeypatch.setattr(tailor_service_mod, "build_llm_provider", lambda cfg: DummyLLM(dim=8))
    res = await BanksService(db_session).get_resume_by_slug(slugify_bank_name("No Legacy Files"))
    assert res is not None

    out = await tailor_service_mod.tailor_resume_from_bank_async(
        bank_folder_name=res.slug,
        jd_text="python backend",
        task_id=None,
    )
    assert out.bank_folder_name == res.slug
    assert out.resume_id


@pytest.mark.asyncio
async def test_api_banks_reads_from_postgres_only(db_session):
    # Create a resume in Postgres without touching local disk.
    res = await BanksService(db_session).create_bank_from_resume_text(
        bank_name="PG Only",
        resume_text="\\section{Skills}\\begin{itemize}\\item Python\\end{itemize}",
        source_format="latex",
        overwrite=False,
    )
    slug = slugify_bank_name("PG Only")
    assert slug == "pg-only"

    rows = (await db_session.execute(select(Resume).where(Resume.id == res.resume_id))).scalars().all()
    assert rows and rows[0].slug == slug

    data = await banks_mod.api_list_banks(session=db_session)
    assert any(b["bank_folder_name"] == slug for b in data["banks"])
