from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import streamlit as st

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.bank_generator.bank_builder import list_banks  # noqa: E402
from app.bank_generator.folder_manager import get_bank_paths  # noqa: E402
from app.config import DEFAULT_CONFIG  # noqa: E402
from app.ui.api.bank_preview_api import compute_stats, load_index_jsonl, tree_for_expected_dirs  # noqa: E402
from app.ui.api.experience_banks_api import list_bank_files, read_bank_file  # noqa: E402


st.title("Preview Experience Bank")
st.caption("Read-only file viewer: folder tree on the left, rendered preview on the right.")

banks = list_banks()
bank_names = [b.bank_folder_name for b in banks]
selected = st.selectbox("Select bank_folder_name", options=[""] + bank_names, index=0)

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
col1.metric("Total files", stats.total_files)
col2.metric("Markdown files", stats.total_md_files)
col3.metric("Vector chunks", stats.total_chunks)
col4.metric("Evidence claims", stats.total_evidence_claims)

st.write(
    {
        "metrics_available": stats.metrics_available,
        "tools_found_top": stats.tools_found[:20],
        "supported_domains_top": stats.supported_domains[:20],
    }
)

files = list_bank_files(paths.bank_folder_name)
if not files:
    st.warning("No previewable files found in this bank.")
    st.stop()

# Build grouped tree for UI
tree_ui: dict[str, list[dict[str, Any]]] = {}
for f in files:
    tree_ui.setdefault(f.folder, []).append(f.__dict__)
for k in tree_ui:
    tree_ui[k].sort(key=lambda x: x["path"])

st.session_state.setdefault("bank_preview_selected_path", "")
st.session_state.setdefault("bank_preview_raw", False)
st.session_state.setdefault("bank_preview_search", "")
st.session_state.setdefault("bank_preview_fullscreen", False)

left, right = st.columns([1, 2])

with left:
    st.subheader("Files")
    st.session_state.bank_preview_search = st.text_input(
        "Search", value=st.session_state.bank_preview_search, placeholder="Filter files…"
    )
    st.session_state.bank_preview_raw = st.checkbox("Raw view", value=st.session_state.bank_preview_raw)

    query = st.session_state.bank_preview_search.strip().casefold()

    def _matches(item: dict[str, Any]) -> bool:
        if not query:
            return True
        hay = f"{item.get('path','')} {item.get('title','')} {item.get('filename','')}".casefold()
        return query in hay

    # Folder-grouped clickable list (tree-like)
    for folder in [
        "work_experience",
        "projects",
        "capabilities",
        "deployment",
        "metrics",
        "reusable_resume_blocks",
        "summaries",
        "metadata",
    ]:
        items = [x for x in tree_ui.get(folder, []) if _matches(x)]
        st.markdown(f"**{folder}/**")
        if not items:
            st.caption("(empty)")
            continue
        for item in items[:250]:
            label = item.get("title") or item.get("filename") or item.get("path")
            secondary = item.get("path")
            if st.button(label, key=f"filebtn:{paths.bank_folder_name}:{secondary}", use_container_width=True):
                st.session_state.bank_preview_selected_path = secondary
            st.caption(secondary)

    if not st.session_state.bank_preview_selected_path:
        st.session_state.bank_preview_selected_path = files[0].path

with right:
    sel = st.session_state.bank_preview_selected_path
    rel_path, title, content = read_bank_file(paths.bank_folder_name, sel)

    head_cols = st.columns([3, 1, 1])
    head_cols[0].subheader(title)
    if head_cols[1].button("Copy content"):
        st.session_state["_copy_buffer"] = content
        st.toast("Copied to session buffer (use Raw view to copy from code block).")
    if head_cols[2].button("Full screen"):
        st.session_state.bank_preview_fullscreen = True

    st.caption(rel_path)
    def _render() -> None:
        if st.session_state.bank_preview_raw or not rel_path.endswith(".md"):
            st.code(content, language="markdown" if rel_path.endswith(".md") else "json")
        else:
            st.markdown(content)

    if st.session_state.bank_preview_fullscreen:
        with st.container(border=True):
            st.subheader("Full screen preview")
            if st.button("Close full screen"):
                st.session_state.bank_preview_fullscreen = False
            _render()
    else:
        _render()

    idx_rows = load_index_jsonl(vec_dir / "index.jsonl")
    file_abs = str((bank_dir / rel_path).resolve())
    matching = []
    for r in idx_rows:
        md = r.get("metadata")
        if not isinstance(md, dict):
            continue
        if md.get("bank_folder_name") != paths.bank_folder_name:
            continue
        if md.get("source_file") == file_abs:
            matching.append(
                {
                    "chunk_id": r.get("chunk_id"),
                    "title": md.get("title"),
                    "metrics_available": md.get("metrics_available"),
                    "evidence_ids": md.get("evidence_ids", []),
                }
            )
    st.subheader("Metadata")
    st.write({"chunks_for_file": len(matching)})
    st.json(matching[:80])
