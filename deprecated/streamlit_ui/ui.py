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
st.sidebar.code(f"LLM_PROVIDER={DEFAULT_CONFIG.llm_provider}")
if DEFAULT_CONFIG.llm_provider == "ollama":
    st.session_state.setdefault("ollama_base_url", DEFAULT_CONFIG.ollama_base_url)
    st.session_state.setdefault("ollama_model", DEFAULT_CONFIG.ollama_model)
    st.session_state.setdefault("ollama_embed_model", DEFAULT_CONFIG.ollama_embedding_model)
    st.session_state.ollama_base_url = st.sidebar.text_input("Ollama base URL", value=st.session_state.ollama_base_url)
    st.session_state.ollama_model = st.sidebar.text_input("Ollama model", value=st.session_state.ollama_model)
    st.session_state.ollama_embed_model = st.sidebar.text_input("Ollama embed model", value=st.session_state.ollama_embed_model)
    st.sidebar.caption("If you see “model not found”, run `ollama list` and `ollama pull <model>`.")
elif DEFAULT_CONFIG.llm_provider == "openai":
    st.sidebar.text_input("OpenAI base URL", value=DEFAULT_CONFIG.openai_base_url, disabled=True)
    st.sidebar.text_input("OpenAI model", value=DEFAULT_CONFIG.openai_model, disabled=True)
    st.sidebar.text_input("OpenAI embed model", value=DEFAULT_CONFIG.openai_embedding_model, disabled=True)
    st.sidebar.caption("Keys are read from environment variables only (not shown in UI).")
else:
    st.sidebar.text_input("Base URL", value=DEFAULT_CONFIG.openai_compatible_base_url or "", disabled=True)
    st.sidebar.text_input("Model", value=DEFAULT_CONFIG.openai_compatible_model or "", disabled=True)
    st.sidebar.text_input("Embed model", value=DEFAULT_CONFIG.openai_compatible_embedding_model or "", disabled=True)
    st.sidebar.caption("Keys are read from environment variables only (not shown in UI).")

_PAGES_DIR = Path(__file__).resolve().parent / "ui" / "pages"
_LANDING = _PAGES_DIR / "0_landing.py"
_CREATE = _PAGES_DIR / "1_create_experience_bank.py"
_TAILOR = _PAGES_DIR / "2_tailor_resume.py"
_PREVIEW = _PAGES_DIR / "3_preview_experience_bank.py"
_LATEX_WS = _PAGES_DIR / "4_resume_latex_preview.py"
_DOCS = _PAGES_DIR / "5_docs.py"
if not _CREATE.exists() or not _TAILOR.exists():
    st.error("UI pages not found. Expected files under `app/ui/pages/`.")
    st.code(str(_CREATE))
    st.code(str(_TAILOR))
    st.stop()

landing = st.Page(str(_LANDING), title="Home", icon="🏠") if _LANDING.exists() else None
create_bank = st.Page(str(_CREATE), title="Create Experience Bank", icon="🧱")
tailor = st.Page(str(_TAILOR), title="Tailor Resume", icon="✍️")
preview = st.Page(str(_PREVIEW), title="Preview Experience Bank", icon="🔎")
latex_ws = st.Page(str(_LATEX_WS), title="Resume Workspace", icon="🧾")
docs = st.Page(str(_DOCS), title="Docs", icon="📚") if _DOCS.exists() else None

pages = [p for p in [landing, create_bank, preview, tailor, latex_ws, docs] if p is not None]
nav = st.navigation(pages)
nav.run()
