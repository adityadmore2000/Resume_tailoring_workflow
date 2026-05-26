from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ResumeNode
from app.resume_tree.errors import CycleError, InvalidOperationError, NotFoundError
from app.resume_tree.tree_build import build_tree


@dataclass(frozen=True)
class NodeCreate:
    node_type: str
    title: str | None = None
    content: dict | None = None
    order_index: int | None = None
    metadata: dict | None = None


@dataclass(frozen=True)
class NodePatch:
    node_type: str | None = None
    title: str | None = None
    content: dict | None = None
    order_index: int | None = None
    metadata: dict | None = None


class ResumeTreeService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def insert_node(self, parent_id: uuid.UUID, node_data: NodeCreate) -> ResumeNode:
        parent = await self._get_node(parent_id)
        if not node_data.node_type.strip():
            raise InvalidOperationError("node_type is required")

        order_index = node_data.order_index
        if order_index is None:
            order_index = await self._next_order_index(parent_id=parent.id)

        node = ResumeNode(
            resume_id=parent.resume_id,
            parent_id=parent.id,
            node_type=node_data.node_type,
            title=node_data.title,
            content=node_data.content,
            order_index=order_index,
            metadata_=(node_data.metadata or {}),
        )
        self._session.add(node)
        await self._session.commit()
        await self._session.refresh(node)
        return node

    async def update_node(self, node_id: uuid.UUID, patch: NodePatch) -> ResumeNode:
        node = await self._get_node(node_id)
        if node.parent_id is None:
            raise InvalidOperationError("Root node cannot be updated via ResumeTreeService")

        values: dict = {}
        if patch.node_type is not None:
            if not patch.node_type.strip():
                raise InvalidOperationError("node_type cannot be empty")
            values["node_type"] = patch.node_type
        if patch.title is not None:
            values["title"] = patch.title
        if patch.content is not None:
            values["content"] = patch.content
        if patch.order_index is not None:
            values["order_index"] = patch.order_index
        if patch.metadata is not None:
            values["metadata_"] = patch.metadata

        if not values:
            return node

        await self._session.execute(
            update(ResumeNode).where(ResumeNode.id == node_id).values(**values)
        )
        await self._session.commit()
        await self._session.refresh(node)
        return node

    async def delete_node(self, node_id: uuid.UUID) -> None:
        node = await self._get_node(node_id)
        if node.parent_id is None:
            raise InvalidOperationError("Root node cannot be deleted")

        has_children = await self._session.scalar(
            select(func.count()).select_from(ResumeNode).where(ResumeNode.parent_id == node_id)
        )
        if (has_children or 0) > 0:
            raise InvalidOperationError("Node is not a leaf; use delete_subtree()")

        await self._session.execute(delete(ResumeNode).where(ResumeNode.id == node_id))
        await self._session.commit()

    async def delete_subtree(self, node_id: uuid.UUID) -> None:
        node = await self._get_node(node_id)
        if node.parent_id is None:
            raise InvalidOperationError("Root node cannot be deleted")

        descendant_ids = await self._descendant_ids(node_id)
        await self._session.execute(delete(ResumeNode).where(ResumeNode.id.in_(descendant_ids)))
        await self._session.commit()

    async def move_node(self, node_id: uuid.UUID, new_parent_id: uuid.UUID, new_order_index: int) -> ResumeNode:
        node = await self._get_node(node_id)
        if node.parent_id is None:
            raise InvalidOperationError("Root node cannot be moved")

        new_parent = await self._get_node(new_parent_id)
        if new_parent.resume_id != node.resume_id:
            raise InvalidOperationError("Cannot move nodes across resumes")

        if node_id == new_parent_id:
            raise CycleError("Cannot parent a node to itself")

        descendant_ids = await self._descendant_ids(node_id)
        if new_parent_id in descendant_ids:
            raise CycleError("Move would create a cycle")

        await self._session.execute(
            update(ResumeNode)
            .where(ResumeNode.id == node_id)
            .values(parent_id=new_parent_id, order_index=new_order_index)
        )
        await self._session.commit()
        await self._session.refresh(node)
        return node

    async def reorder_children(self, parent_id: uuid.UUID, ordered_node_ids: list[uuid.UUID]) -> None:
        parent = await self._get_node(parent_id)
        existing_ids = (
            await self._session.execute(
                select(ResumeNode.id).where(ResumeNode.parent_id == parent.id).order_by(ResumeNode.order_index)
            )
        ).scalars().all()

        if set(existing_ids) != set(ordered_node_ids) or len(existing_ids) != len(ordered_node_ids):
            raise InvalidOperationError("ordered_node_ids must exactly match current children")

        for idx, nid in enumerate(ordered_node_ids):
            await self._session.execute(
                update(ResumeNode).where(ResumeNode.id == nid).values(order_index=idx)
            )
        await self._session.commit()

    async def retrieve_full_resume_tree(self, resume_id: uuid.UUID) -> dict:
        nodes = (
            await self._session.execute(
                select(ResumeNode)
                .where(ResumeNode.resume_id == resume_id)
                .order_by(ResumeNode.parent_id.nullsfirst(), ResumeNode.order_index, ResumeNode.created_at)
            )
        ).scalars().all()
        return {"resume_id": str(resume_id), "roots": build_tree(nodes)}

    async def _get_node(self, node_id: uuid.UUID) -> ResumeNode:
        node = await self._session.get(ResumeNode, node_id)
        if node is None:
            raise NotFoundError(f"Node not found: {node_id}")
        return node

    async def _next_order_index(self, *, parent_id: uuid.UUID) -> int:
        v = await self._session.scalar(
            select(func.coalesce(func.max(ResumeNode.order_index), -1) + 1).where(ResumeNode.parent_id == parent_id)
        )
        return int(v or 0)

    async def _descendant_ids(self, node_id: uuid.UUID) -> list[uuid.UUID]:
        sql = text(
            """
            WITH RECURSIVE descendants AS (
              SELECT id, parent_id
              FROM resume_nodes
              WHERE id = :node_id
              UNION ALL
              SELECT rn.id, rn.parent_id
              FROM resume_nodes rn
              JOIN descendants d ON rn.parent_id = d.id
            )
            SELECT id FROM descendants
            """
        )
        rows = (await self._session.execute(sql, {"node_id": node_id})).all()
        return [r[0] for r in rows]
