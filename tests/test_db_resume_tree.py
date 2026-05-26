from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select


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
