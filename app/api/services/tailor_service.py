from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from app.config import DEFAULT_CONFIG
from app.db.session import get_sessionmaker
from app.db.models import Resume, ResumeNode
from app.generated_resumes.latex_compiler import LatexCompileError, compile_resume_latex
from app.generated_resumes.resume_store import init_generated_resume, new_resume_id
from app.llm.factory import build_llm_provider
from app.tailoring.jd_parser import parse_jd
from app.rewriter import rewrite_bullet
from app.verifier import latex_to_plain_for_checks, verify_bullet_rewrite
from app.resume_tree.qdrant_index import QdrantResumeNodesIndex, ResumeNodesIndexConfig, nodes_collection_name
from app.tailoring.hierarchy_context import build_tailoring_context
from app.tasks.task_progress import TASKS


class TailorError(ValueError):
    pass


@dataclass(frozen=True)
class TailorResult:
    bank_folder_name: str
    resume_id: str
    messages: list[str]


def _apply_replacements(source_tex: str, replacements: list[tuple[int, int, str]]) -> str:
    out = source_tex
    for start, end, new_text in sorted(replacements, key=lambda r: r[0], reverse=True):
        out = out[:start] + new_text + out[end:]
    return out


async def tailor_resume_from_bank_async(*, bank_folder_name: str, jd_text: str, task_id: str | None = None) -> TailorResult:
    if not bank_folder_name.strip():
        raise TailorError("bank_name is required")
    if not jd_text.strip():
        raise TailorError("jd_text is required")

    cfg = DEFAULT_CONFIG
    llm = build_llm_provider(cfg)

    qurl = (cfg.qdrant_url or "").strip()
    if not qurl:
        raise TailorError("QDRANT_URL is not set; resume_nodes semantic retrieval requires Qdrant.")

    sessionmaker = get_sessionmaker()
    messages: list[str] = []
    async with sessionmaker() as session:
        from sqlalchemy import select

        slug = bank_folder_name.strip()
        resume_obj = (await session.execute(select(Resume).where(Resume.slug == slug))).scalar_one_or_none()
        if resume_obj is None:
            raise TailorError(f"Resume not found for bank_folder_name='{bank_folder_name}'.")

        source_tex = (resume_obj.metadata_ or {}).get("source_resume_tex") if isinstance(resume_obj.metadata_, dict) else None
        if not isinstance(source_tex, str) or not source_tex.strip():
            raise TailorError(
                "Resume source LaTeX is missing from Postgres metadata. Re-create the bank so `resumes.metadata.source_resume_tex` is populated."
            )

        nodes = (
            await session.execute(
                select(ResumeNode)
                .where(ResumeNode.resume_id == resume_obj.id)
                .order_by(ResumeNode.parent_id.nullsfirst(), ResumeNode.order_index, ResumeNode.created_at)
            )
        ).scalars().all()
        if not nodes:
            raise TailorError("Resume has no resume_nodes in Postgres; cannot tailor.")

    if task_id:
        TASKS.advance(task_id=task_id, step_id="resume_parsed")

    jd_struct = parse_jd(jd_text, llm)
    if task_id:
        TASKS.advance(task_id=task_id, step_id="jd_analyzed")

    index = QdrantResumeNodesIndex(
        cfg=ResumeNodesIndexConfig(url=qurl, collection=nodes_collection_name()),
        llm=llm,
    )

    # Ensure searchable nodes are indexed (idempotent).
    to_delete: list[uuid.UUID] = []
    for n in nodes:
        ok, _reasons = index.index_decision(n)
        if ok:
            index.upsert_node(n)
        else:
            to_delete.append(n.id)
    if to_delete:
        index.delete_nodes(to_delete)

    # Semantic retrieval (resume-scoped).
    qvec = index.embed((jd_text or "")[:4000])
    hits = index.search(resume_id=resume_obj.id, query_vector=qvec, limit=12)
    matched_node_ids: list[uuid.UUID] = []
    for h in hits:
        try:
            matched_node_ids.append(uuid.UUID(str(h.get("node_id") or "")))
        except Exception:
            continue

    context, context_debug = build_tailoring_context(nodes=nodes, matched_node_ids=matched_node_ids)

    if task_id:
        TASKS.advance(task_id=task_id, step_id="experience_matched")

    # Determine rewrite candidates from hierarchy context.
    evidence_detail_node_ids = set()
    for x in context_debug.get("evidence_detail_node_ids", []):
        try:
            evidence_detail_node_ids.add(uuid.UUID(str(x)))
        except Exception:
            continue

    allowed: list[str] = []
    seen_allowed: set[str] = set()
    for n in nodes:
        md = n.metadata_ or {}
        if not isinstance(md, dict):
            continue
        for k in ("tools", "skills"):
            v = md.get(k)
            if not isinstance(v, list):
                continue
            for t in v:
                s = str(t).strip()
                if not s:
                    continue
                key = s.casefold()
                if key in seen_allowed:
                    continue
                seen_allowed.add(key)
                allowed.append(s)

    jd_keywords = jd_struct.important_keywords + jd_struct.required_skills + jd_struct.preferred_skills

    replacements: list[tuple[int, int, str]] = []
    rewrite_debug: list[dict[str, object]] = []
    rewrites_used = 0
    max_rewrites = 18

    for n in nodes:
        if n.id not in evidence_detail_node_ids:
            continue
        if n.parent_id is None:
            continue
        md = n.metadata_ or {}
        if not isinstance(md, dict):
            messages.append(f"Node {n.id} metadata is not a dict; skipped rewrite.")
            continue
        imm = md.get("immutable_fields")
        if not isinstance(imm, dict):
            messages.append(f"Node {n.id} missing metadata.immutable_fields; skipped rewrite.")
            continue
        try:
            span_start = int(imm.get("span_start"))
            span_end = int(imm.get("span_end"))
        except Exception:
            messages.append(f"Node {n.id} missing valid immutable_fields.span_start/span_end; skipped rewrite.")
            continue
        if span_start < 0 or span_end <= span_start or span_end > len(source_tex):
            messages.append(f"Node {n.id} has out-of-range spans ({span_start}, {span_end}); skipped rewrite.")
            continue

        if rewrites_used >= max_rewrites:
            rewrite_debug.append({"node_id": str(n.id), "action": "keep", "reason": "rewrite_limit_reached"})
            continue

        content = n.content or {}
        if not isinstance(content, dict):
            content = {}
        original_latex = str(content.get("latex") or "").strip()
        if not original_latex:
            # Fall back to source slice (still bullet content span)
            original_latex = source_tex[span_start:span_end].strip()
        original_plain = str((content.get("plain") or md.get("source_text") or "")).strip()
        if not original_plain:
            original_plain = latex_to_plain_for_checks(original_latex)

        try:
            out = rewrite_bullet(
                bullet_latex=original_latex,
                bullet_plain=original_plain,
                jd_keywords=jd_keywords,
                role_focus=jd_struct.role_focus,
                allowed_tools_and_skills=allowed,
                llm=llm,
            )
        except Exception as e:
            rewrite_debug.append({"node_id": str(n.id), "action": "keep", "reason": f"rewrite_failed: {e}"})
            continue

        candidate_latex = (out.suggested_latex or "").strip()
        candidate_plain = latex_to_plain_for_checks(candidate_latex)
        vr = verify_bullet_rewrite(
            original_latex=original_latex,
            original_plain=original_plain,
            candidate_latex=candidate_latex,
            candidate_plain=candidate_plain,
            jd_keywords=jd_keywords,
            allowed_tools_and_skills=allowed,
            cfg=cfg,
        )
        if not vr.ok:
            rewrite_debug.append(
                {
                    "node_id": str(n.id),
                    "action": "keep",
                    "reason": "verifier_rejected",
                    "flags": [f.model_dump() for f in vr.flags],
                }
            )
            continue

        replacements.append((span_start, span_end, candidate_latex))
        rewrites_used += 1
        rewrite_debug.append({"node_id": str(n.id), "action": "rewrite", "span_start": span_start, "span_end": span_end})

    tailored_tex = _apply_replacements(source_tex, replacements)
    if task_id:
        TASKS.advance(task_id=task_id, step_id="content_tailored")

    resume_id = new_resume_id()

    gen_paths = init_generated_resume(
        bank_folder_name=bank_folder_name,
        resume_id=resume_id,
        latex=tailored_tex,
        markdown=None,
        text=None,
        traceability={
            "resume_id": str(resume_obj.id),
            "bank_folder_name": bank_folder_name,
            "matched_node_ids": [str(x) for x in matched_node_ids],
            "context": context,
            "context_debug": context_debug,
            "rewrite_debug": rewrite_debug,
            "messages": list(messages),
        },
    )

    try:
        compile_resume_latex(paths=gen_paths)
    except LatexCompileError as e:
        messages.append(str(e))

    if task_id:
        TASKS.advance(task_id=task_id, step_id="finalized")
        TASKS.set_result(task_id=task_id, result={"bank_folder_name": bank_folder_name, "resume_id": resume_id, "messages": messages})
        TASKS.complete(task_id=task_id)
    return TailorResult(bank_folder_name=bank_folder_name, resume_id=resume_id, messages=messages)


def tailor_resume_from_bank(*, bank_folder_name: str, jd_text: str, task_id: str | None = None) -> TailorResult:
    """
    Sync wrapper for background task runners.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(tailor_resume_from_bank_async(bank_folder_name=bank_folder_name, jd_text=jd_text, task_id=task_id))
    # If invoked from an async context, require using the async entrypoint.
    raise TailorError("tailor_resume_from_bank() cannot be called from a running event loop; use tailor_resume_from_bank_async().")
