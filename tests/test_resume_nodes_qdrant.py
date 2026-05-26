from __future__ import annotations

import uuid

import pytest
from qdrant_client.http.models import FieldCondition, Filter, MatchValue
from sqlalchemy import select

from app.db.models import Resume, ResumeNode
from app.rag.qdrant_store import QdrantConfig, get_client
from app.resume_tree.qdrant_index import QdrantResumeNodesIndex, ResumeNodesIndexConfig
from app.resume_tree.semantic_search import retrieve_relevant_nodes_for_jd
from app.resume_tree.service import NodeCreate, NodePatch, ResumeTreeService


class DummyLLM:
    def __init__(self, dim: int = 8):
        self._dim = dim

    def embed_text(self, text: str) -> list[float]:
        return [0.1] * self._dim


async def _make_resume_with_root(db_session, *, slug: str) -> tuple[uuid.UUID, uuid.UUID]:
    resume = Resume(slug=slug, title=slug, metadata_={})
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    root = ResumeNode(
        resume_id=resume.id,
        parent_id=None,
        node_type="resume_root",
        title="root",
        content=None,
        order_index=0,
        metadata_={},
    )
    db_session.add(root)
    await db_session.commit()
    await db_session.refresh(root)
    return resume.id, root.id


@pytest.mark.asyncio
async def test_insert_searchable_node_indexes_qdrant(db_session):
    cfg = ResumeNodesIndexConfig(url=":memory:", collection="nodes_idx_1")
    index = QdrantResumeNodesIndex(cfg=cfg, llm=DummyLLM(dim=8))
    client = get_client(QdrantConfig(url=cfg.url, collection=cfg.collection))

    resume_id, root_id = await _make_resume_with_root(db_session, slug="r1")
    svc = ResumeTreeService(db_session, semantic_index=index)

    node = await svc.insert_node(root_id, NodeCreate(node_type="experience", title="Acme", content={"t": "x"}))

    f = Filter(must=[FieldCondition(key="resume_id", match=MatchValue(value=str(resume_id)))])
    res = client.count(collection_name=cfg.collection, count_filter=f, exact=True)
    assert int(res.count or 0) == 1

    pts = client.retrieve(collection_name=cfg.collection, ids=[str(node.id)], with_payload=True)
    assert pts and (pts[0].payload or {}).get("node_id") == str(node.id)


@pytest.mark.asyncio
async def test_update_node_reindexes_qdrant(db_session):
    cfg = ResumeNodesIndexConfig(url=":memory:", collection="nodes_idx_2")
    index = QdrantResumeNodesIndex(cfg=cfg, llm=DummyLLM(dim=8))
    client = get_client(QdrantConfig(url=cfg.url, collection=cfg.collection))

    _, root_id = await _make_resume_with_root(db_session, slug="r2")
    svc = ResumeTreeService(db_session, semantic_index=index)

    node = await svc.insert_node(root_id, NodeCreate(node_type="project", title="Old", content={"t": "x"}))
    await svc.update_node(node.id, NodePatch(title="New"))

    pts = client.retrieve(collection_name=cfg.collection, ids=[str(node.id)], with_payload=True)
    assert (pts[0].payload or {}).get("title") == "New"


@pytest.mark.asyncio
async def test_delete_subtree_deletes_qdrant_points(db_session):
    cfg = ResumeNodesIndexConfig(url=":memory:", collection="nodes_idx_3")
    index = QdrantResumeNodesIndex(cfg=cfg, llm=DummyLLM(dim=8))
    client = get_client(QdrantConfig(url=cfg.url, collection=cfg.collection))

    resume_id, root_id = await _make_resume_with_root(db_session, slug="r3")
    svc = ResumeTreeService(db_session, semantic_index=index)

    parent = await svc.insert_node(root_id, NodeCreate(node_type="experience", title="E1"))
    child = await svc.insert_node(parent.id, NodeCreate(node_type="bullet", content={"text": "did x"}))

    await svc.delete_subtree(parent.id)

    f = Filter(must=[FieldCondition(key="resume_id", match=MatchValue(value=str(resume_id)))])
    res = client.count(collection_name=cfg.collection, count_filter=f, exact=True)
    assert int(res.count or 0) == 0
    assert await db_session.get(ResumeNode, child.id) is None


@pytest.mark.asyncio
async def test_retrieval_returns_node_ids_and_is_scoped_to_resume(db_session):
    cfg = ResumeNodesIndexConfig(url=":memory:", collection="nodes_idx_4")
    index = QdrantResumeNodesIndex(cfg=cfg, llm=DummyLLM(dim=8))

    resume1_id, root1_id = await _make_resume_with_root(db_session, slug="r4a")
    resume2_id, root2_id = await _make_resume_with_root(db_session, slug="r4b")

    svc1 = ResumeTreeService(db_session, semantic_index=index)
    n1 = await svc1.insert_node(root1_id, NodeCreate(node_type="summary", title="S", content={"text": "python"}))

    svc2 = ResumeTreeService(db_session, semantic_index=index)
    n2 = await svc2.insert_node(root2_id, NodeCreate(node_type="summary", title="Other", content={"text": "k8s"}))

    out = await retrieve_relevant_nodes_for_jd(session=db_session, index=index, resume_id=resume1_id, jd_text="python", top_k=5)
    matched = set(out["matched_node_ids"])
    assert str(n1.id) in matched
    assert str(n2.id) not in matched
    assert out["tree"]["resume_id"] == str(resume1_id)

