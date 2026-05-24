from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Ensure repo root import works when running `streamlit run app/ui/app.py`.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.config import DEFAULT_CONFIG  # noqa: E402


def init_state() -> None:
    st.session_state.setdefault("ollama_base_url", DEFAULT_CONFIG.ollama_base_url)
    st.session_state.setdefault("ollama_model", DEFAULT_CONFIG.ollama_model)


# Deprecated: kept for compatibility if someone runs `streamlit run app/ui/app.py`.
# Preferred: `streamlit run app/ui.py` (uses st.navigation and the same pages).
st.set_page_config(page_title="Resume Tailoring KB", layout="wide")
init_state()
st.title("Resume Tailoring KB")
st.caption("Run `streamlit run app/ui.py` for the full multipage app.")
