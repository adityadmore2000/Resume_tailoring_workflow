from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Resume, ResumeNode
from app.parser import parse_latex_resume
from app.resume_tree.hierarchy_inference import canonical_section_label


def slugify_bank_name(name: str) -> str:
    s = name.strip().casefold()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "bank"


@dataclass(frozen=True)
class CreateBankResult:
    resume_id: uuid.UUID
    slug: str
    root_id: uuid.UUID


class BanksService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_resumes(self) -> list[Resume]:
        return (
            await self._session.execute(select(Resume).order_by(Resume.updated_at.desc(), Resume.created_at.desc()))
        ).scalars().all()

    async def get_resume_by_slug(self, slug: str) -> Resume | None:
        return (await self._session.execute(select(Resume).where(Resume.slug == slug))).scalar_one_or_none()

    async def create_bank_from_resume_text(
        self,
        *,
        bank_name: str,
        resume_text: str,
        source_format: str,
        overwrite: bool,
    ) -> CreateBankResult:
        slug = slugify_bank_name(bank_name)

        existing = await self.get_resume_by_slug(slug)
        if existing is not None:
            if not overwrite:
                raise ValueError("Bank already exists (set overwrite=true to replace).")
            await self._session.execute(delete(Resume).where(Resume.id == existing.id))
            await self._session.commit()

        resume = Resume(
            slug=slug,
            title=bank_name.strip() or slug,
            metadata_={
                "source_format": source_format,
                # Phase 5: persist source resume inside Postgres (no local experience_bank dependency).
                "source_resume_tex": resume_text if source_format != "text" else "",
                "source_resume_text": resume_text if source_format == "text" else "",
            },
        )
        self._session.add(resume)
        await self._session.commit()
        await self._session.refresh(resume)

        root = ResumeNode(
            resume_id=resume.id,
            parent_id=None,
            node_type="resume_root",
            title=resume.title,
            content={"source_format": source_format},
            order_index=0,
            metadata_={
                "searchable": False,
                "section_label": "root",
                "inferred_semantic_role": "resume_root",
                "immutable_fields": {},
                "source_text": "",
                "source_section": "",
                "evidence_ids": [],
                "tools": [],
                "skills": [],
                "metrics": {},
            },
        )
        self._session.add(root)
        await self._session.commit()
        await self._session.refresh(root)

        # Parse (LaTeX or plain text treated as raw fallback).
        parsed = parse_latex_resume(resume_text) if source_format == "latex" else parse_latex_resume(resume_text)

        section_nodes: dict[str, ResumeNode] = {}
        for i, sec in enumerate(parsed.sections):
            sec_label = canonical_section_label(sec.name.value if hasattr(sec, "name") else sec.title_raw)
            sec_node = ResumeNode(
                resume_id=resume.id,
                parent_id=root.id,
                node_type="section",
                title=sec.title_raw.strip() or sec.name.value,
                content={"section_name": sec.name.value},
                order_index=i,
                metadata_={
                    "searchable": False,
                    "section_label": sec_label,
                    "inferred_semantic_role": "section",
                    "immutable_fields": {"span_start": sec.span_start, "span_end": sec.span_end},
                    "source_text": sec.raw_text,
                    "source_section": sec.name.value,
                    "evidence_ids": [],
                    "tools": parsed.extracted_tools,
                    "skills": parsed.extracted_skills,
                    "metrics": {},
                },
            )
            self._session.add(sec_node)
            await self._session.flush()
            section_nodes[sec.title_raw] = sec_node

            for j, b in enumerate(sec.bullets):
                item = ResumeNode(
                    resume_id=resume.id,
                    parent_id=sec_node.id,
                    node_type="item",
                    title=None,
                    content={"bullet_id": b.id},
                    order_index=j,
                    metadata_={
                        "searchable": False,
                        "section_label": sec_label,
                        "inferred_semantic_role": f"{sec_label}_item" if sec_label != "other" else "item",
                        "immutable_fields": {"bullet_id": b.id},
                        "source_text": b.plain,
                        "source_section": sec.name.value,
                        "evidence_ids": [],
                        "tools": parsed.extracted_tools,
                        "skills": parsed.extracted_skills,
                        "metrics": {},
                    },
                )
                self._session.add(item)
                await self._session.flush()

                detail = ResumeNode(
                    resume_id=resume.id,
                    parent_id=item.id,
                    node_type="detail",
                    title=None,
                    content={"latex": b.latex, "plain": b.plain},
                    order_index=0,
                    metadata_={
                        "searchable": True,
                        "section_label": sec_label,
                        "inferred_semantic_role": f"{sec_label}_detail" if sec_label != "other" else "detail",
                        "immutable_fields": {"span_start": b.span_start, "span_end": b.span_end, "bullet_id": b.id},
                        "source_text": b.plain,
                        "source_section": sec.name.value,
                        "evidence_ids": [],
                        "tools": parsed.extracted_tools,
                        "skills": parsed.extracted_skills,
                        "metrics": {},
                    },
                )
                self._session.add(detail)

        await self._session.commit()

        return CreateBankResult(resume_id=resume.id, slug=resume.slug, root_id=root.id)

    async def ensure_root_exists(self, resume_id: uuid.UUID) -> ResumeNode:
        root = (
            await self._session.execute(
                select(ResumeNode).where(ResumeNode.resume_id == resume_id, ResumeNode.parent_id.is_(None))
            )
        ).scalar_one_or_none()
        if root is not None:
            return root
        raise RuntimeError("Resume is missing root node")
