from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk


class ResumeNode(Base, TimestampMixin):
    __tablename__ = "resume_nodes"

    id: Mapped[uuid.UUID] = uuid_pk()

    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resume_nodes.id", ondelete="CASCADE"),
        nullable=True,
    )

    node_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    resume: Mapped["Resume"] = relationship(back_populates="nodes")
    parent: Mapped["ResumeNode | None"] = relationship(
        remote_side="ResumeNode.id",
        back_populates="children",
        foreign_keys=[parent_id],
    )
    children: Mapped[list["ResumeNode"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_resume_nodes_resume_id", "resume_id"),
        Index("ix_resume_nodes_parent_id", "parent_id"),
    )
