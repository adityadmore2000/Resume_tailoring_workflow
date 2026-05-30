from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class RenderableNode:
    node_id: uuid.UUID
    parent_id: uuid.UUID | None
    node_type: str
    title: str | None
    content: dict | None
    metadata: dict
    order_index: int
    children: list["RenderableNode"] = field(default_factory=list)


@dataclass(frozen=True)
class RenderableResume:
    resume_id: uuid.UUID
    slug: str
    title: str
    roots: list[RenderableNode]

