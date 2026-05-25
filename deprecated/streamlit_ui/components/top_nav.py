from __future__ import annotations

import streamlit as st


def render_top_nav(*, active: str | None = None) -> None:
    """Lightweight, workflow-driven navigation (no admin-dashboard sidebar)."""

    with st.container(border=True):
        cols = st.columns([2, 1, 1, 1, 1])
        with cols[0]:
            st.page_link("ui/pages/0_landing.py", label="Evidence-Grounded Resume Tailoring", icon="🏠")
        with cols[1]:
            st.page_link("ui/pages/1_create_experience_bank.py", label="Experience Banks", icon="🧱")
        with cols[2]:
            st.page_link("ui/pages/2_tailor_resume.py", label="Tailor Resume", icon="✍️")
        with cols[3]:
            st.page_link("ui/pages/4_resume_latex_preview.py", label="Workspace", icon="🧾")
        with cols[4]:
            st.page_link("ui/pages/5_docs.py", label="Docs", icon="📚")

        if active:
            st.caption(f"You're here: **{active}**")
