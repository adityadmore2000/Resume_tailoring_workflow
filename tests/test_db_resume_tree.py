from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text


def _test_database_url() -> str | None:
    url = (os.environ.get("TEST_DATABASE_URL") or "").strip()
    return url or None


@pytest.fixture(scope="session")
def db_url() -> str:
    url = _test_database_url()
    if not url:
        pytest.skip("Set TEST_DATABASE_URL (or DATABASE_URL) to run Postgres-backed DB tests.")
    return url


@pytest.fixture(scope="session", autouse=True)
def _run_migrations(db_url: str) -> None:
    os.environ["DATABASE_URL"] = db_url
    repo_root = Path(__file__).resolve().parents[1]
    cfg = Config(str(repo_root / "alembic.ini"))
    command.upgrade(cfg, "head")


@pytest.fixture()
async def db_session(db_url: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", db_url)
    from app.db.session import get_sessionmaker

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(text("TRUNCATE resume_nodes, resumes RESTART IDENTITY CASCADE"))
        await session.commit()
        yield session


@pytest.mark.asyncio
async def test_create_resume_and_nodes(db_session):
    from app.db.models import Resume, ResumeNode

    resume = Resume(title="My Resume", metadata_={"source": "test"})
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    root = ResumeNode(
        resume_id=resume.id,
        parent_id=None,
        node_type="root",
        title="Root",
        content={"kind": "root"},
        order_index=0,
        metadata_={},
    )
    db_session.add(root)
    await db_session.commit()
    await db_session.refresh(root)

    child = ResumeNode(
        resume_id=resume.id,
        parent_id=root.id,
        node_type="section",
        title="Child",
        content={"kind": "section"},
        order_index=1,
        metadata_={"x": 1},
    )
    db_session.add(child)
    await db_session.commit()
    await db_session.refresh(child)

    assert isinstance(resume.id, uuid.UUID)
    assert root.parent_id is None
    assert child.parent_id == root.id


@pytest.mark.asyncio
async def test_fetch_nodes_by_resume_id(db_session):
    from app.db.models import Resume, ResumeNode

    resume = Resume(title="R", metadata_={})
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    root = ResumeNode(
        resume_id=resume.id,
        parent_id=None,
        node_type="root",
        title=None,
        content=None,
        order_index=0,
        metadata_={},
    )
    db_session.add(root)
    await db_session.commit()
    await db_session.refresh(root)

    child = ResumeNode(
        resume_id=resume.id,
        parent_id=root.id,
        node_type="leaf",
        title="C",
        content={"t": "x"},
        order_index=0,
        metadata_={},
    )
    db_session.add(child)
    await db_session.commit()

    rows = (await db_session.execute(select(ResumeNode).where(ResumeNode.resume_id == resume.id))).scalars().all()
    assert {n.id for n in rows} == {root.id, child.id}
    assert sum(1 for n in rows if n.parent_id is None) == 1
