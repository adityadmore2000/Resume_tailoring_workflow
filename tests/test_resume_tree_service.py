from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.db.models import Resume, ResumeNode
from app.resume_tree.errors import CycleError, InvalidOperationError
from app.resume_tree.service import NodeCreate, NodePatch, ResumeTreeService


async def _make_resume_with_root(db_session) -> tuple[uuid.UUID, uuid.UUID]:
    resume = Resume(slug="r", title="R", metadata_={})
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    root = ResumeNode(
        resume_id=resume.id,
        parent_id=None,
        node_type="root",
        title="root",
        content={"kind": "root"},
        order_index=0,
        metadata_={},
    )
    db_session.add(root)
    await db_session.commit()
    await db_session.refresh(root)
    return resume.id, root.id


@pytest.mark.asyncio
async def test_insert_section_experience_bullet(db_session):
    resume_id, root_id = await _make_resume_with_root(db_session)
    svc = ResumeTreeService(db_session)

    section = await svc.insert_node(root_id, NodeCreate(node_type="section", title="Experience"))
    exp = await svc.insert_node(section.id, NodeCreate(node_type="experience", title="Acme"))
    bullet = await svc.insert_node(exp.id, NodeCreate(node_type="bullet", content={"text": "Did X"}))

    rows = (
        await db_session.execute(select(ResumeNode).where(ResumeNode.resume_id == resume_id))
    ).scalars().all()
    assert {n.id for n in rows} == {root_id, section.id, exp.id, bullet.id}


@pytest.mark.asyncio
async def test_update_leaf_only(db_session):
    _, root_id = await _make_resume_with_root(db_session)
    svc = ResumeTreeService(db_session)

    section = await svc.insert_node(root_id, NodeCreate(node_type="section", title="S"))
    bullet = await svc.insert_node(section.id, NodeCreate(node_type="bullet", content={"text": "old"}))

    await svc.update_node(bullet.id, NodePatch(content={"text": "new"}, metadata={"a": 1}))

    refreshed_section = await db_session.get(ResumeNode, section.id)
    refreshed_bullet = await db_session.get(ResumeNode, bullet.id)
    assert refreshed_section is not None and refreshed_section.title == "S"
    assert refreshed_bullet is not None and refreshed_bullet.content == {"text": "new"}
    assert refreshed_bullet.metadata_ == {"a": 1}


@pytest.mark.asyncio
async def test_delete_leaf(db_session):
    _, root_id = await _make_resume_with_root(db_session)
    svc = ResumeTreeService(db_session)

    section = await svc.insert_node(root_id, NodeCreate(node_type="section", title="S"))
    bullet = await svc.insert_node(section.id, NodeCreate(node_type="bullet", content={"text": "x"}))

    await svc.delete_node(bullet.id)
    assert await db_session.get(ResumeNode, bullet.id) is None
    assert await db_session.get(ResumeNode, section.id) is not None


@pytest.mark.asyncio
async def test_delete_subtree(db_session):
    _, root_id = await _make_resume_with_root(db_session)
    svc = ResumeTreeService(db_session)

    section = await svc.insert_node(root_id, NodeCreate(node_type="section", title="S"))
    exp = await svc.insert_node(section.id, NodeCreate(node_type="experience", title="E"))
    bullet = await svc.insert_node(exp.id, NodeCreate(node_type="bullet", content={"t": "x"}))

    await svc.delete_subtree(section.id)
    assert await db_session.get(ResumeNode, section.id) is None
    assert await db_session.get(ResumeNode, exp.id) is None
    assert await db_session.get(ResumeNode, bullet.id) is None
    assert await db_session.get(ResumeNode, root_id) is not None


@pytest.mark.asyncio
async def test_move_node(db_session):
    _, root_id = await _make_resume_with_root(db_session)
    svc = ResumeTreeService(db_session)

    s1 = await svc.insert_node(root_id, NodeCreate(node_type="section", title="S1"))
    s2 = await svc.insert_node(root_id, NodeCreate(node_type="section", title="S2"))
    exp = await svc.insert_node(s1.id, NodeCreate(node_type="experience", title="E"))

    await svc.move_node(exp.id, s2.id, new_order_index=0)
    moved = await db_session.get(ResumeNode, exp.id)
    assert moved is not None and moved.parent_id == s2.id and moved.order_index == 0


@pytest.mark.asyncio
async def test_reorder_children(db_session):
    _, root_id = await _make_resume_with_root(db_session)
    svc = ResumeTreeService(db_session)

    a = await svc.insert_node(root_id, NodeCreate(node_type="section", title="A"))
    b = await svc.insert_node(root_id, NodeCreate(node_type="section", title="B"))
    c = await svc.insert_node(root_id, NodeCreate(node_type="section", title="C"))

    await svc.reorder_children(root_id, [c.id, a.id, b.id])
    rows = (
        await db_session.execute(
            select(ResumeNode.id, ResumeNode.order_index).where(ResumeNode.parent_id == root_id).order_by(ResumeNode.order_index)
        )
    ).all()
    assert [r[0] for r in rows] == [c.id, a.id, b.id]
    assert [r[1] for r in rows] == [0, 1, 2]


@pytest.mark.asyncio
async def test_prevent_cycles_on_move(db_session):
    _, root_id = await _make_resume_with_root(db_session)
    svc = ResumeTreeService(db_session)

    section = await svc.insert_node(root_id, NodeCreate(node_type="section", title="S"))
    child = await svc.insert_node(section.id, NodeCreate(node_type="section", title="C"))

    with pytest.raises(CycleError):
        await svc.move_node(section.id, child.id, new_order_index=0)


@pytest.mark.asyncio
async def test_root_never_auto_deleted(db_session):
    _, root_id = await _make_resume_with_root(db_session)
    svc = ResumeTreeService(db_session)

    with pytest.raises(InvalidOperationError):
        await svc.delete_node(root_id)
    with pytest.raises(InvalidOperationError):
        await svc.delete_subtree(root_id)


@pytest.mark.asyncio
async def test_retrieve_full_resume_tree(db_session):
    resume_id, root_id = await _make_resume_with_root(db_session)
    svc = ResumeTreeService(db_session)

    section = await svc.insert_node(root_id, NodeCreate(node_type="section", title="S"))
    _ = await svc.insert_node(section.id, NodeCreate(node_type="bullet", content={"text": "x"}))

    tree = await svc.retrieve_full_resume_tree(resume_id)
    assert tree["resume_id"] == str(resume_id)
    assert len(tree["roots"]) == 1
    assert tree["roots"][0]["id"] == str(root_id)
