from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.ui.components.top_nav import render_top_nav  # noqa: E402


st.title("Evidence-Grounded AI Resume Tailoring")
st.caption(
    "Convert your master resume into a reusable knowledge base and generate recruiter-focused resumes using verified evidence retrieval."
)

render_top_nav(active="Home")

hero = st.columns([2, 1], gap="large")
with hero[0]:
    st.markdown(
        "\n".join(
            [
                "### Guided workflow studio (not a file browser)",
                "",
                "This platform introduces a workflow paradigm:",
                "",
                "**Resume → Experience Bank → Retrieval → Tailored Resume → LaTeX Workspace → PDF Export**",
            ]
        )
    )
    ctas = st.columns([1, 1, 2])
    ctas[0].page_link("ui/pages/1_create_experience_bank.py", label="Create Experience Bank", icon="🧱", use_container_width=True)
    ctas[1].page_link("ui/pages/5_docs.py", label="View Workflow", icon="🧭", use_container_width=True)
with hero[1]:
    with st.container(border=True):
        st.markdown("**Why this exists**")
        st.write(
            "Most AI resume tools blindly rewrite text. This system retrieves only evidence-backed experience from structured Experience Banks before generating anything."
        )

st.divider()
st.markdown("## Workflow")

st.graphviz_chart(
    """
digraph workflow {
  rankdir=TB;
  node [shape=box, style="rounded,filled", fillcolor="#F8FAFC", color="#CBD5E1", fontname="Inter"];
  edge [color="#94A3B8"];
  "Master Resume" -> "Experience Bank";
  "Experience Bank" -> "Semantic Retrieval";
  "Semantic Retrieval" -> "Verified Tailoring";
  "Verified Tailoring" -> "LaTeX Resume Workspace";
  "LaTeX Resume Workspace" -> "PDF Export";
}
""".strip()
)

st.divider()
st.markdown("## What you get")

cards1 = st.columns(3, gap="large")
with cards1[0].container(border=True):
    st.markdown("### Experience Banks")
    st.write("Upload once. Your bank becomes the reusable source-of-truth for future tailoring.")
with cards1[1].container(border=True):
    st.markdown("### Evidence-Grounded Tailoring")
    st.write("Only verified evidence is retrieved and assembled into role-relevant bullets.")
with cards1[2].container(border=True):
    st.markdown("### Traceability")
    st.write("Generated bullets map back to specific evidence so you can audit and edit confidently.")

cards2 = st.columns(2, gap="large")
with cards2[0].container(border=True):
    st.markdown("### LaTeX Resume Workspace")
    st.write("Edit LaTeX, recompile, preview PDF, and export recruiter-ready output.")
with cards2[1].container(border=True):
    st.markdown("### Recruiter-Oriented Assembly")
    st.write("The system focuses on role fit: relevance, clarity, and evidence-backed claims.")

st.divider()
with st.container(border=True):
    st.markdown("## Next step")
    st.write("Start by creating an Experience Bank from your master resume.")
    actions = st.columns([1, 1, 2])
    actions[0].page_link("ui/pages/1_create_experience_bank.py", label="Create Experience Bank", icon="🧱", use_container_width=True)
    actions[1].page_link("ui/pages/2_tailor_resume.py", label="Tailor Resume", icon="✍️", use_container_width=True)

