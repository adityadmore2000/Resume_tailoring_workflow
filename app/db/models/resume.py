from __future__ import annotations

import uuid

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk


class Resume(Base, TimestampMixin):
    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = uuid_pk()

    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    nodes: Mapped[list["ResumeNode"]] = relationship(
        back_populates="resume",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (Index("ux_resumes_slug", "slug", unique=True),)
