from __future__ import annotations

import inspect

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import select

import app.api.routers.banks as banks_mod
import app.api.routers.tailor as tailor_mod
import app.api.services.tailor_service as tailor_service_mod
import app.api.routers.retrieve_debug as retrieve_debug_mod
from app.banks_pg.service import slugify_bank_name
from app.banks_pg.service import BanksService
from app.db.models import Resume, ResumeNode
from app.generated_resumes.resume_store import get_generated_resume_paths, read_latex
from app.generated_resumes.resume_store import read_traceability
from app.schemas import JDAnalysis
from app.rewriter import BulletRewriteOut
from app.resume_tree.latex_renderer import render_resume_to_latex
from app.resume_tree.renderable import RenderableNode, RenderableResume
from app.resume_tree.render_mapper import resume_nodes_to_renderable


class DummyLLM:
    def __init__(self, dim: int = 8):
        self._dim = dim

    def embed_text(self, text: str) -> list[float]:
        return [0.1] * self._dim

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]

    def generate_text(self, *, system: str, user: str) -> str:
        return "{}"

    def generate_json(self, *, system: str, user: str, schema, max_retries: int = 1, allow_fallback: bool = True):
        if schema is JDAnalysis:
            return JDAnalysis(required_skills=["python"], preferred_skills=[], role_focus=["backend"], important_keywords=["fastapi"])
        if schema is BulletRewriteOut:
            return BulletRewriteOut(suggested_latex="Improved bullet.", rationale="deterministic stub")
        return schema.model_validate({})


async def _run_background_tasks(bg: BackgroundTasks) -> None:
    for t in list(bg.tasks):
        res = t.func(*t.args, **t.kwargs)
        if inspect.isawaitable(res):
            await res


def test_tree_renderer_renders_without_spans_and_applies_overrides():
    import uuid

    resume_id = uuid.uuid4()
    root_id = uuid.uuid4()
    sec_id = uuid.uuid4()
    item_id = uuid.uuid4()
    detail_id = uuid.uuid4()

    detail = RenderableNode(
        node_id=detail_id,
        parent_id=item_id,
        node_type="detail",
        title=None,
        content={"plain": "A & B"},
        metadata={},  # no spans
        order_index=0,
        children=[],
    )
    item = RenderableNode(
        node_id=item_id,
        parent_id=sec_id,
        node_type="item",
        title=None,
        content={},
        metadata={},
        order_index=0,
        children=[detail],
    )
    sec = RenderableNode(
        node_id=sec_id,
        parent_id=root_id,
        node_type="section",
        title="Experience",
        content={},
        metadata={},
        order_index=0,
        children=[item],
    )
    root = RenderableNode(
        node_id=root_id,
        parent_id=None,
        node_type="resume_root",
        title="My Resume",
        content={},
        metadata={},
        order_index=0,
        children=[sec],
    )
    r = RenderableResume(resume_id=resume_id, slug="x", title="My Resume", roots=[root])

    latex = render_resume_to_latex(resume=r, bullet_overrides={detail_id: "Overridden bullet."})
    assert "\\documentclass" in latex
    assert "\\section*{Experience}" in latex
    assert "Overridden bullet." in latex


def test_tree_renderer_escapes_special_characters_in_plain_text():
    import uuid

    resume_id = uuid.uuid4()
    root_id = uuid.uuid4()
    sec_id = uuid.uuid4()
    item_id = uuid.uuid4()
    detail_id = uuid.uuid4()

    plain = r"Cost $1,300+; 15% improvement; R&D; model_name; C#; {x} ~ ^ \\"

    detail = RenderableNode(
        node_id=detail_id,
        parent_id=item_id,
        node_type="detail",
        title=None,
        content={"plain": plain},
        metadata={},
        order_index=0,
        children=[],
    )
    item = RenderableNode(node_id=item_id, parent_id=sec_id, node_type="item", title=None, content={}, metadata={}, order_index=0, children=[detail])
    sec = RenderableNode(node_id=sec_id, parent_id=root_id, node_type="section", title="Summary", content={}, metadata={}, order_index=0, children=[item])
    root = RenderableNode(node_id=root_id, parent_id=None, node_type="resume_root", title="R", content={}, metadata={}, order_index=0, children=[sec])
    r = RenderableResume(resume_id=resume_id, slug="x", title="R", roots=[root])

    latex = render_resume_to_latex(resume=r, bullet_overrides=None)
    assert r"\$1,300+" in latex
    assert r"15\%" in latex
    assert r"R\&D" in latex
    assert r"model\_name" in latex
    assert r"C\#" in latex
    assert r"\{x\}" in latex
    assert r"\textasciitilde{}" in latex
    assert r"\textasciicircum{}" in latex
    # Backslash escapes to \\textbackslash{} but braces are escaped too (\\{\\}).
    assert r"\textbackslash" in latex


def test_tree_renderer_prefers_plain_over_imported_latex_by_default():
    import uuid

    resume_id = uuid.uuid4()
    root_id = uuid.uuid4()
    sec_id = uuid.uuid4()
    item_id = uuid.uuid4()
    detail_id = uuid.uuid4()

    detail = RenderableNode(
        node_id=detail_id,
        parent_id=item_id,
        node_type="detail",
        title=None,
        content={"latex": "IMPORTED LATEX", "plain": "Edited plain"},
        metadata={},
        order_index=0,
        children=[],
    )
    item = RenderableNode(node_id=item_id, parent_id=sec_id, node_type="item", title=None, content={}, metadata={}, order_index=0, children=[detail])
    sec = RenderableNode(node_id=sec_id, parent_id=root_id, node_type="section", title="Projects", content={}, metadata={}, order_index=0, children=[item])
    root = RenderableNode(node_id=root_id, parent_id=None, node_type="resume_root", title="R", content={}, metadata={}, order_index=0, children=[sec])
    r = RenderableResume(resume_id=resume_id, slug="x", title="R", roots=[root])

    latex = render_resume_to_latex(resume=r, bullet_overrides=None)
    assert "Edited plain" in latex
    assert "IMPORTED LATEX" not in latex


def test_tree_renderer_can_preserve_imported_latex_when_enabled():
    import uuid

    resume_id = uuid.uuid4()
    root_id = uuid.uuid4()
    sec_id = uuid.uuid4()
    item_id = uuid.uuid4()
    detail_id = uuid.uuid4()

    detail = RenderableNode(
        node_id=detail_id,
        parent_id=item_id,
        node_type="detail",
        title=None,
        content={"latex": "\\textbf{Imported}", "plain": "Edited plain"},
        metadata={},
        order_index=0,
        children=[],
    )
    item = RenderableNode(node_id=item_id, parent_id=sec_id, node_type="item", title=None, content={}, metadata={}, order_index=0, children=[detail])
    sec = RenderableNode(node_id=sec_id, parent_id=root_id, node_type="section", title="Skills", content={}, metadata={}, order_index=0, children=[item])
    root = RenderableNode(node_id=root_id, parent_id=None, node_type="resume_root", title="R", content={}, metadata={}, order_index=0, children=[sec])
    r = RenderableResume(resume_id=resume_id, slug="x", title="R", roots=[root])

    latex = render_resume_to_latex(resume=r, bullet_overrides=None, preserve_imported_latex=True)
    assert "\\textbf{Imported}" in latex


def test_resume_nodes_to_renderable_and_renderer_contains_test_marker_without_db():
    import uuid

    resume_id = uuid.uuid4()
    root_id = uuid.uuid4()
    section_id = uuid.uuid4()
    item_id = uuid.uuid4()
    detail_id = uuid.uuid4()

    resume = Resume(slug="u", title="Unit Resume", metadata_={})
    resume.id = resume_id  # type: ignore[assignment]

    root = ResumeNode(
        resume_id=resume_id,
        parent_id=None,
        node_type="resume_root",
        title="Unit Resume",
        content={},
        order_index=0,
        metadata_={},
    )
    root.id = root_id  # type: ignore[assignment]

    section = ResumeNode(
        resume_id=resume_id,
        parent_id=root_id,
        node_type="section",
        title="Experience",
        content={},
        order_index=0,
        metadata_={},
    )
    section.id = section_id  # type: ignore[assignment]

    item = ResumeNode(
        resume_id=resume_id,
        parent_id=section_id,
        node_type="item",
        title=None,
        content={},
        order_index=0,
        metadata_={},
    )
    item.id = item_id  # type: ignore[assignment]

    detail = ResumeNode(
        resume_id=resume_id,
        parent_id=item_id,
        node_type="detail",
        title=None,
        content={"plain": "TEST_TREE_RENDER_NODE_123", "latex": "TEST_TREE_RENDER_NODE_123"},
        order_index=0,
        metadata_={"searchable": True, "source_text": "TEST_TREE_RENDER_NODE_123"},
    )
    detail.id = detail_id  # type: ignore[assignment]

    renderable = resume_nodes_to_renderable(resume=resume, nodes=[root, section, item, detail])
    latex = render_resume_to_latex(resume=renderable, bullet_overrides=None)
    # Render uses plain-text escaping by default, so underscores are escaped.
    assert r"TEST\_TREE\_RENDER\_NODE\_123" in latex


@pytest.mark.asyncio
async def test_resume_nodes_can_render_full_latex_document(db_session):
    # Create a bank (resume + nodes).
    bg = BackgroundTasks()
    _ = await banks_mod.api_create_bank(
        background_tasks=bg,
        bank_name="Render Bank",
        overwrite=False,
        source_format="latex",
        file=None,
        resume_text="\\section{Experience}\\begin{itemize}\\item Built X in Python\\end{itemize}",
    )
    await _run_background_tasks(bg)

    slug = slugify_bank_name("Render Bank")
    resume = (await db_session.execute(select(Resume).where(Resume.slug == slug))).scalar_one()
    nodes = (
        await db_session.execute(select(ResumeNode).where(ResumeNode.resume_id == resume.id).order_by(ResumeNode.order_index))
    ).scalars().all()

    renderable = resume_nodes_to_renderable(resume=resume, nodes=nodes)
    latex = render_resume_to_latex(resume=renderable, bullet_overrides=None)

    assert "\\documentclass" in latex
    assert "\\begin{document}" in latex
    assert "\\section*{Experience}" in latex
    assert "\\item" in latex
    assert "Built X in Python" in latex
    assert latex.strip().endswith("\\end{document}")


@pytest.mark.asyncio
async def test_tailoring_generation_does_not_require_source_resume_tex_or_spans(db_session, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QDRANT_URL", ":memory:")
    monkeypatch.delenv("LEGACY_TEX_SPAN_PATCH", raising=False)

    # Patch LLM provider to be deterministic (and ensure rewrite produces a known string).
    monkeypatch.setattr(tailor_service_mod, "build_llm_provider", lambda cfg: DummyLLM(dim=8))
    monkeypatch.setattr(retrieve_debug_mod, "build_llm_provider", lambda cfg: DummyLLM(dim=8))

    # Create bank in Postgres.
    bg = BackgroundTasks()
    _ = await banks_mod.api_create_bank(
        background_tasks=bg,
        bank_name="Tree Bank",
        overwrite=False,
        source_format="latex",
        file=None,
        resume_text="\\section{Projects}\\begin{itemize}\\item Shipped API\\end{itemize}",
    )
    await _run_background_tasks(bg)

    slug = slugify_bank_name("Tree Bank")
    resume = (await db_session.execute(select(Resume).where(Resume.slug == slug))).scalar_one()

    # Remove provenance source LaTeX so generation cannot depend on it.
    md = dict(resume.metadata_ or {})
    md.pop("source_resume_tex", None)
    resume.metadata_ = md
    await db_session.commit()

    # Corrupt spans for all detail nodes (should not matter for tree rendering).
    nodes = (await db_session.execute(select(ResumeNode).where(ResumeNode.resume_id == resume.id))).scalars().all()
    for n in nodes:
        if n.node_type != "detail":
            continue
        mdn = dict(n.metadata_ or {})
        imm = dict(mdn.get("immutable_fields") or {})
        imm["span_start"] = -999
        imm["span_end"] = -998
        mdn["immutable_fields"] = imm
        n.metadata_ = mdn
    await db_session.commit()

    # Tailor via router; run background tasks inline.
    bg2 = BackgroundTasks()
    resp = await tailor_mod.api_tailor(
        body=tailor_mod.TailorRequest(bank_name="Tree Bank", jd_text="Python backend FastAPI"),
        background_tasks=bg2,
        session=db_session,
    )
    await _run_background_tasks(bg2)

    # Read generated LaTeX: should be full doc and include rewritten bullet text.
    prog = tailor_service_mod.TASKS.get(resp.task_id)
    assert prog is not None
    assert prog.status == "completed"
    gen_resume_id = prog.result.get("resume_id")
    paths = get_generated_resume_paths(bank_folder_name=slug, resume_id=gen_resume_id)
    latex, _updated_at = read_latex(paths)

    assert "\\documentclass" in latex
    assert "\\section*{Projects}" in latex
    assert "Improved bullet." in latex


@pytest.mark.asyncio
async def test_tailoring_output_comes_from_tree_not_source_resume_tex_and_reports_tree_mode(db_session, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QDRANT_URL", ":memory:")
    monkeypatch.delenv("LEGACY_TEX_SPAN_PATCH", raising=False)
    monkeypatch.delenv("PRESERVE_IMPORTED_LATEX", raising=False)

    monkeypatch.setattr(tailor_service_mod, "build_llm_provider", lambda cfg: DummyLLM(dim=8))
    monkeypatch.setattr(retrieve_debug_mod, "build_llm_provider", lambda cfg: DummyLLM(dim=8))

    bg = BackgroundTasks()
    _ = await banks_mod.api_create_bank(
        background_tasks=bg,
        bank_name="Source Tex Bank",
        overwrite=False,
        source_format="latex",
        file=None,
        resume_text="\\section{Experience}\\begin{itemize}\\item OLD\\end{itemize}",
    )
    await _run_background_tasks(bg)

    slug = slugify_bank_name("Source Tex Bank")
    resume = (await db_session.execute(select(Resume).where(Resume.slug == slug))).scalar_one()

    # Plant a provenance LaTeX that must never appear in the generated output.
    md = dict(resume.metadata_ or {})
    md["source_resume_tex"] = "SHOULD_NOT_APPEAR_FROM_SOURCE_TEX"
    resume.metadata_ = md
    await db_session.commit()

    # Force the tree content marker.
    nodes = (await db_session.execute(select(ResumeNode).where(ResumeNode.resume_id == resume.id))).scalars().all()
    target = next((n for n in nodes if n.node_type == "detail"), None)
    assert target is not None
    target.content = {"plain": "SHOULD_APPEAR_FROM_TREE", "latex": ""}  # ensure renderer uses plain
    await db_session.commit()

    out = await tailor_service_mod.tailor_resume_from_bank_async(bank_folder_name=slug, jd_text="anything", task_id=None)
    paths = get_generated_resume_paths(bank_folder_name=slug, resume_id=out.resume_id)
    latex, _ = read_latex(paths)
    trace = read_traceability(paths)

    assert "SHOULD_APPEAR_FROM_TREE" in latex
    assert "SHOULD_NOT_APPEAR_FROM_SOURCE_TEX" not in latex
    assert isinstance(trace, dict)
    debug = (trace.get("debug") or {}) if isinstance(trace, dict) else {}
    assert debug.get("generation_mode") == "tree_renderer"


@pytest.mark.asyncio
async def test_generation_succeeds_with_missing_or_invalid_spans_and_no_source_tex(db_session, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QDRANT_URL", ":memory:")
    monkeypatch.delenv("LEGACY_TEX_SPAN_PATCH", raising=False)

    monkeypatch.setattr(tailor_service_mod, "build_llm_provider", lambda cfg: DummyLLM(dim=8))

    res = await BanksService(db_session).create_bank_from_resume_text(
        bank_name="Spanless",
        resume_text="\\section{Projects}\\begin{itemize}\\item One\\end{itemize}",
        source_format="latex",
        overwrite=False,
    )
    resume = (await db_session.execute(select(Resume).where(Resume.id == res.resume_id))).scalar_one()
    md = dict(resume.metadata_ or {})
    md.pop("source_resume_tex", None)
    resume.metadata_ = md
    await db_session.commit()

    nodes = (await db_session.execute(select(ResumeNode).where(ResumeNode.resume_id == resume.id))).scalars().all()
    for n in nodes:
        mdn = dict(n.metadata_ or {})
        if "immutable_fields" in mdn:
            mdn["immutable_fields"] = {"span_start": -1, "span_end": -1}
        n.metadata_ = mdn
    await db_session.commit()

    out = await tailor_service_mod.tailor_resume_from_bank_async(bank_folder_name=resume.slug, jd_text="x", task_id=None)
    paths = get_generated_resume_paths(bank_folder_name=resume.slug, resume_id=out.resume_id)
    latex, _ = read_latex(paths)
    assert "\\documentclass" in latex
