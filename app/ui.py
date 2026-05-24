from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Entrypoint for the new two-phase product flow.
# We use `st.navigation` so pages can live under `app/ui/pages/` while still running:
# `streamlit run app/ui.py`
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.config import DEFAULT_CONFIG  # noqa: E402


st.set_page_config(page_title="Resume Tailoring KB", layout="wide")

st.sidebar.subheader("LLM Settings")
st.session_state.setdefault("ollama_base_url", DEFAULT_CONFIG.ollama_base_url)
st.session_state.setdefault("ollama_model", DEFAULT_CONFIG.ollama_model)
st.session_state.ollama_base_url = st.sidebar.text_input("Ollama base URL", value=st.session_state.ollama_base_url)
st.session_state.ollama_model = st.sidebar.text_input("Ollama model", value=st.session_state.ollama_model)
st.sidebar.caption("If you see “model not found”, run `ollama list` and `ollama pull <model>`.")

_PAGES_DIR = Path(__file__).resolve().parent / "ui" / "pages"
_CREATE = _PAGES_DIR / "1_create_experience_bank.py"
_TAILOR = _PAGES_DIR / "2_tailor_resume.py"
if not _CREATE.exists() or not _TAILOR.exists():
    st.error("UI pages not found. Expected files under `app/ui/pages/`.")
    st.code(str(_CREATE))
    st.code(str(_TAILOR))
    st.stop()

create_bank = st.Page(str(_CREATE), title="Create Experience Bank", icon="🧱")
tailor = st.Page(str(_TAILOR), title="Tailor Resume", icon="✍️")

nav = st.navigation([create_bank, tailor])
nav.run()
