from __future__ import annotations

import inspect

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select

import app.api.routers.banks as banks_mod
from app.banks_pg.service import slugify_bank_name
from app.db.models import Resume, ResumeNode
from app.resume_tree.service import ResumeTreeService


async def _run_background_tasks(bg: BackgroundTasks) -> None:
    for t in list(bg.tasks):
        res = t.func(*t.args, **t.kwargs)
        if inspect.isawaitable(res):
            await res


@pytest.mark.asyncio
async def test_create_bank_creates_resume_tree(db_session, tmp_path):
    assert not (tmp_path / "experience_bank").exists()

    bg = BackgroundTasks()
    resp = await banks_mod.api_create_bank(
        background_tasks=bg,
        bank_name="My Bank",
        overwrite=False,
        source_format="latex",
        file=None,
        resume_text="\\section{Experience}\\begin{itemize}\\item Built X\\end{itemize}",
    )
    assert resp.bank_folder_name == slugify_bank_name("My Bank")
    await _run_background_tasks(bg)

    resumes = (await db_session.execute(select(Resume))).scalars().all()
    assert len(resumes) == 1

    nodes = (await db_session.execute(select(ResumeNode))).scalars().all()
    assert any(n.parent_id is None and n.node_type == "resume_root" for n in nodes)
    assert any(n.node_type == "section" for n in nodes)


@pytest.mark.asyncio
async def test_get_banks_lists_resumes(db_session):
    bg = BackgroundTasks()
    await banks_mod.api_create_bank(
        background_tasks=bg,
        bank_name="Bank One",
        overwrite=False,
        source_format="latex",
        file=None,
        resume_text="\\section{Skills}\\begin{itemize}\\item Python\\end{itemize}",
    )
    await _run_background_tasks(bg)

    data = await banks_mod.api_list_banks(session=db_session)
    assert "banks" in data
    assert any(b["bank_folder_name"] == slugify_bank_name("Bank One") for b in data["banks"])


@pytest.mark.asyncio
async def test_full_tree_is_retrievable(db_session):
    bg = BackgroundTasks()
    await banks_mod.api_create_bank(
        background_tasks=bg,
        bank_name="Tree Bank",
        overwrite=False,
        source_format="latex",
        file=None,
        resume_text="\\section{Experience}\\begin{itemize}\\item Did Y\\end{itemize}",
    )
    await _run_background_tasks(bg)

    bank = await banks_mod.api_get_bank("Tree Bank", session=db_session)
    assert bank["bank"]["bank_folder_name"] == slugify_bank_name("Tree Bank")

    r = (await db_session.execute(select(Resume).where(Resume.slug == bank["bank"]["bank_folder_name"]))).scalar_one()
    tsvc = ResumeTreeService(db_session)
    tree = await tsvc.retrieve_full_resume_tree(r.id)
    assert tree["resume_id"] == str(r.id)
    assert tree["roots"]


@pytest.mark.asyncio
async def test_runtime_does_not_require_local_experience_bank_files(db_session, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bg = BackgroundTasks()
    await banks_mod.api_create_bank(
        background_tasks=bg,
        bank_name="No Files",
        overwrite=False,
        source_format="latex",
        file=None,
        resume_text="\\section{Projects}\\begin{itemize}\\item Shipped Z\\end{itemize}",
    )
    await _run_background_tasks(bg)
    assert not (tmp_path / "experience_bank").exists()
    assert not (tmp_path / "banks_registry.json").exists()


def test_legacy_delete_endpoint_disabled():
    with pytest.raises(HTTPException) as e:
        banks_mod.api_delete_bank("any")
    assert e.value.status_code == 501
