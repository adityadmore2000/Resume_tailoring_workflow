from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.bank_generator.bank_builder import list_banks  # noqa: E402
from app.bank_generator.folder_manager import get_bank_paths  # noqa: E402
from app.config import DEFAULT_CONFIG  # noqa: E402
from app.tailoring.resume_assembler import load_bank_index  # noqa: E402
from app.ui.api.bank_preview_api import compute_stats  # noqa: E402
from app.ui.api.experience_banks_api import BankItemSummary, list_bank_items  # noqa: E402
from app.ui.components.top_nav import render_top_nav  # noqa: E402


st.title("Preview Experience Bank")
st.caption("Step 2 of 4 — Review extracted experience, projects, and evidence before tailoring.")
render_top_nav(active="Preview Experience Bank")

with st.container(border=True):
    st.subheader("Step 2 of 4 — Review Experience Bank")
    st.markdown(
        "\n".join(
            [
                "Review extracted capabilities, projects, and evidence in a **human-readable** view.",
                "",
                "**Recommended next step:** open Tailor Resume after you've confirmed the content looks accurate.",
            ]
        )
    )
    with st.expander("How this works"):
        st.markdown(
            "\n".join(
                [
                    "- The left navigation groups items into Experience / Projects / Capabilities.",
                    "- The center panel shows recruiter-facing content and linked evidence.",
                    "- Technical metadata stays collapsed by default to keep the review focused.",
                ]
            )
        )

banks = list_banks()
bank_names = [b.bank_folder_name for b in banks]
if not bank_names:
    st.selectbox(
        "Experience Bank",
        options=[],
        index=None,
        placeholder="No Experience Banks found",
        disabled=True,
    )
    st.page_link(
        "ui/pages/1_create_experience_bank.py",
        label="Create Experience Bank",
        icon="🧱",
        use_container_width=True,
    )
    st.stop()

selected = st.selectbox(
    "Experience Bank",
    options=bank_names,
    index=None,
    placeholder="Select an Experience Bank",
    help="Choose the bank you want to review. This view is designed to be human-readable first, technical second.",
)

if not selected:
    st.info("Select a bank to preview.")
    st.stop()

paths = get_bank_paths(Path(DEFAULT_CONFIG.data_root), selected)
bank_dir = paths.experience_bank_dir
vec_dir = paths.vector_store_dir

if not bank_dir.exists():
    st.error(f"Bank folder not found: {bank_dir}")
    st.stop()

stats = compute_stats(bank_dir, vec_dir, paths.bank_folder_name)
col1, col2, col3, col4 = st.columns(4)
col1.metric("Files", stats.total_files)
col2.metric("KB pages", stats.total_md_files)
col3.metric("Vector chunks", stats.total_chunks)
col4.metric("Evidence claims", stats.total_evidence_claims)

bank_index = load_bank_index(bank_dir)
items = list_bank_items(paths.bank_folder_name, data_root=Path(DEFAULT_CONFIG.data_root))

work_items = [x for x in items if x.type == "work_experience"]
project_items = [x for x in items if x.type == "project"]
cap_items = [x for x in items if x.type == "capability"]

st.session_state.setdefault("bank_preview_search", "")
st.session_state.setdefault("bank_preview_selected_key", "")


def _matches_item(q: str, it: BankItemSummary) -> bool:
    if not q:
        return True
    hay = " ".join(
        [
            it.title,
            it.type,
            it.raw_path,
            " ".join(it.domains or []),
            " ".join(it.tools or []),
            it.date_range or "",
            it.location or "",
        ]
    ).casefold()
    return q in hay


q = st.sidebar.text_input(
    "Search",
    value=st.session_state.bank_preview_search,
    placeholder="Search titles, tools, domains…",
)
st.session_state.bank_preview_search = q
query = q.strip().casefold()


def _sidebar_group(label: str, group_items: list[BankItemSummary]) -> None:
    with st.sidebar.expander(label, expanded=True):
        visible = [it for it in group_items if _matches_item(query, it)]
        if not visible:
            st.caption("No matches")
            return
        for it in visible[:400]:
            key = f"{it.type}:{it.id}"
            selected_now = st.session_state.bank_preview_selected_key == key
            if st.button(
                it.title,
                key=f"nav:{paths.bank_folder_name}:{key}",
                use_container_width=True,
                type=("primary" if selected_now else "secondary"),
            ):
                st.session_state.bank_preview_selected_key = key
                st.rerun()
            if it.type == "work_experience" and (it.date_range or it.location):
                secondary = " · ".join([x for x in [it.date_range, it.location] if x])
                st.caption(secondary)


_sidebar_group("Experience", work_items)
_sidebar_group("Projects", project_items)
_sidebar_group("Capabilities", cap_items)

if not st.session_state.bank_preview_selected_key:
    first = (work_items or project_items or cap_items)
    if first:
        st.session_state.bank_preview_selected_key = f"{first[0].type}:{first[0].id}"
    else:
        st.warning("No previewable items found in this bank.")
        st.stop()


def _find_selected() -> BankItemSummary:
    key = st.session_state.bank_preview_selected_key
    for it in items:
        if f"{it.type}:{it.id}" == key:
            return it
    return items[0]


sel = _find_selected()
claim_by_id = {c.evidence_id: c for c in bank_index.evidence_claims}


def _evidence_ids_for_item(it: BankItemSummary) -> list[str]:
    if it.type == "work_experience":
        w = next((x for x in bank_index.work_experience if x.entry_id == it.id), None)
        return list(w.evidence_ids or []) if w else []
    if it.type == "project":
        p = next((x for x in bank_index.projects if x.project_id == it.id), None)
        return list(p.evidence_ids or []) if p else []
    if it.type == "capability":
        c = next((x for x in bank_index.capabilities if x.capability_id == it.id), None)
        return list(c.evidence_ids or []) if c else []
    return []


eids = _evidence_ids_for_item(sel)

def _chips(items: list[str], *, limit: int = 16) -> str:
    xs = [x.strip() for x in (items or []) if isinstance(x, str) and x.strip()]
    xs = list(dict.fromkeys(xs))[:limit]
    return " ".join(f"`{x}`" for x in xs)

with st.container(border=True):
    st.subheader(sel.title)
    st.caption(f"Type: {sel.type.replace('_', ' ').title()}")
    meta_line = " · ".join([x for x in [sel.date_range, sel.location] if x])
    if meta_line:
        st.caption(meta_line)
    if sel.domains:
        st.markdown(f"**Domains:** {_chips(sel.domains)}")
    if sel.tools:
        st.markdown(f"**Tools:** {_chips(sel.tools)}")

tabs = st.tabs(["Overview", "Evidence", "Resume Bullets", "Technical Metadata"])

with tabs[0]:
    if sel.type == "work_experience":
        w = next((x for x in bank_index.work_experience if x.entry_id == sel.id), None)
        if not w:
            st.info("Work experience entry not found in index.")
        else:
            st.markdown("**Overview**")
            date_range = f"{w.start_date} - {w.end_date}".strip()
            st.markdown(
                "\n".join(
                    [
                        f"- **Company:** {w.company or 'Unclear from resume'}",
                        f"- **Role:** {w.role_title or 'Unclear from resume'}",
                        f"- **Subtitle/domain:** {w.subtitle or 'Unclear from resume'}",
                        f"- **Employment label:** {w.employment_type_or_label or '—'}",
                        f"- **Date range:** {date_range if date_range != '-' else 'Unclear from resume'}",
                        f"- **Location:** {w.location or '—'}",
                    ]
                )
            )
    elif sel.type == "project":
        p = next((x for x in bank_index.projects if x.project_id == sel.id), None)
        if not p:
            st.info("Project not found in index.")
        else:
            st.markdown("**Overview**")
            if p.description:
                st.write(p.description)
            if p.tools:
                st.markdown(f"**Tools:** {_chips(p.tools)}")
            if sel.domains:
                st.markdown(f"**Domains:** {_chips(sel.domains)}")
    else:
        c = next((x for x in bank_index.capabilities if x.capability_id == sel.id), None)
        if not c:
            st.info("Capability not found in index.")
        else:
            st.markdown("**Overview**")
            st.markdown(f"- **Capability:** {c.name}")
            if c.domains:
                st.markdown(f"- **Domains:** {_chips(c.domains)}")
            if c.tools:
                st.markdown(f"- **Tools:** {_chips(c.tools)}")

    if not eids:
        st.info("No evidence linked to this item yet.")

with tabs[1]:
    st.markdown("**Evidence (from resume)**")
    if not eids:
        st.info("No evidence linked to this item.")
    else:
        for eid in eids[:400]:
            c = claim_by_id.get(eid)
            if not c:
                st.caption(f"Missing claim for `{eid}`")
                continue
            title = c.claim_text.strip() if c.claim_text else "Evidence"
            with st.container(border=True):
                st.markdown(title)
                st.caption(f"{c.source_section} · `{c.evidence_id}`")
                preview = (c.source_text or "").strip().replace("\n", " ")
                if len(preview) > 220:
                    preview = preview[:220] + "…"
                if preview:
                    st.write(preview)
                with st.expander("Show full source text"):
                    st.code((c.source_text or "").strip(), language="latex")
                if c.tools:
                    st.caption("Tools: " + ", ".join(c.tools[:30]))
                if c.metrics:
                    st.caption("Metrics: " + ", ".join(c.metrics[:30]))
                if c.notes:
                    st.caption("Notes: " + c.notes)

with tabs[2]:
    st.markdown("**Resume-ready bullets**")
    candidates = []
    if bank_index.reusable_bullets and eids:
        eids_set = set(eids)
        for b in bank_index.reusable_bullets:
            if set(b.evidence_ids or []) & eids_set:
                candidates.append(b)
    if not candidates:
        st.info("Reusable bullets will be generated during JD tailoring and must reference evidence IDs.")
    else:
        for b in candidates[:200]:
            cols = st.columns([6, 1])
            cols[0].code(b.bullet_text, language="text")
            if cols[1].button("Copy", key=f"copybullet:{paths.bank_folder_name}:{sel.type}:{sel.id}:{b.bullet_id}"):
                st.session_state["_copy_buffer"] = b.bullet_text
                st.toast("Copied to session buffer.")
            if b.evidence_ids:
                st.caption("Evidence: " + ", ".join(f"`{x}`" for x in b.evidence_ids[:20]))

with tabs[3]:
    st.markdown("**Technical metadata (debug)**")
    st.caption("Hidden by default during normal review. Use this only when debugging traceability/indexing.")
    st.write({"raw_path": sel.raw_path})
    st.write({"item": sel.__dict__})
    st.write({"evidence_ids": eids[:500]})
    if st.checkbox("Show full bank index JSON (large)", value=False):
        st.json(bank_index.model_dump())
