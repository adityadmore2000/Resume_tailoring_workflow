from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.ui.components.top_nav import render_top_nav  # noqa: E402


st.title("Docs")
st.caption("Workflow-oriented help, designed to be read inside the product.")
render_top_nav(active="Docs")

DOCS_DIR = (_ROOT / "docs").resolve()

doc_files: list[tuple[str, Path]] = [
    ("Getting Started", DOCS_DIR / "getting-started.md"),
    ("Experience Banks", DOCS_DIR / "experience-banks.md"),
    ("Tailoring", DOCS_DIR / "tailoring.md"),
    ("Traceability", DOCS_DIR / "traceability.md"),
    ("Resume Workspace", DOCS_DIR / "resume-workspace.md"),
    ("FAQ", DOCS_DIR / "faq.md"),
    ("Local Setup", DOCS_DIR / "local-setup.md"),
    ("Deployment", DOCS_DIR / "deployment.md"),
]

labels = [x[0] for x in doc_files]
selected_label = st.selectbox("Select a doc", options=labels, index=0, placeholder="Choose a doc page")
selected = next((p for (lbl, p) in doc_files if lbl == selected_label), doc_files[0][1])

with st.container(border=True):
    st.subheader(selected_label)
    if selected.exists():
        st.markdown(selected.read_text(encoding="utf-8"))
    else:
        st.info("This doc page hasn't been created yet.")
        st.caption(f"Expected file: `{selected}`")

st.divider()
st.markdown("### Recommended next steps")
next_cols = st.columns([1, 1, 1, 2])
next_cols[0].page_link("ui/pages/1_create_experience_bank.py", label="Create Experience Bank", icon="🧱", use_container_width=True)
next_cols[1].page_link("ui/pages/3_preview_experience_bank.py", label="Preview Bank", icon="🔎", use_container_width=True)
next_cols[2].page_link("ui/pages/2_tailor_resume.py", label="Tailor Resume", icon="✍️", use_container_width=True)

