from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.bank_generator.bank_builder import generate_experience_bank  # noqa: E402
from app.bank_generator.folder_manager import BankFolderError, get_bank_paths  # noqa: E402
from app.config import DEFAULT_CONFIG  # noqa: E402
from app.llm import LLMError, OllamaClient  # noqa: E402
from app.resume_parser.section_detector import looks_like_latex  # noqa: E402


st.title("Create Experience Bank")
st.caption("Upload a master resume once → generate an evidence-grounded KB + per-bank vector index.")

bank_name = st.text_input("Bank folder name (required)", placeholder="e.g., aditya_ai_master_resume")
overwrite = st.checkbox("Overwrite existing bank (requires confirmation)", value=False)
confirm_overwrite = st.checkbox("I understand overwrite may replace an existing bank", value=False, disabled=not overwrite)

uploaded = st.file_uploader("Upload resume (.tex / .txt)", type=["tex", "txt"])
resume_text = ""
source_format = "latex"
if uploaded is not None:
    resume_text = uploaded.read().decode("utf-8", errors="replace")
    source_format = "latex" if uploaded.name.endswith(".tex") else "text"

resume_text = st.text_area("Or paste resume text/LaTeX", value=resume_text, height=260)

if resume_text and source_format == "latex" and not looks_like_latex(resume_text):
    st.warning("This does not look like LaTeX. It will be treated as plain text in a future update (MVP expects LaTeX).")

if st.button("Generate Experience Bank", type="primary", use_container_width=True):
    if not bank_name.strip():
        st.error("Bank folder name is required.")
        st.stop()
    if not resume_text.strip():
        st.error("Resume content is required.")
        st.stop()
    if overwrite and not confirm_overwrite:
        st.error("Confirm overwrite to proceed.")
        st.stop()

    llm = OllamaClient(base_url=st.session_state.ollama_base_url, model=st.session_state.ollama_model)
    try:
        # Pre-check existence for friendly UI.
        paths = get_bank_paths(Path(DEFAULT_CONFIG.data_root), bank_name)
        if (paths.experience_bank_dir.exists() or paths.vector_store_dir.exists()) and not overwrite:
            st.warning(f"Bank `{paths.bank_folder_name}` already exists. Enable overwrite to replace it.")
            st.stop()

        with st.status("Generating experience bank…", expanded=True) as status:
            st.write("Parsing resume")
            st.write("Extracting atomic evidence")
            st.write("Validating schemas")
            st.write("Writing KB markdown")
            st.write("Ingesting into vector store")
            st.write("Updating registry")
            res = generate_experience_bank(
                resume_tex=resume_text,
                bank_folder_name=bank_name,
                llm=llm,
                overwrite=overwrite,
                source_format=source_format,
            )
            if res.messages:
                for m in res.messages:
                    st.info(m)
            if not res.validation.ok:
                status.update(label="Bank generation failed", state="error")
                st.json({"errors": res.validation.errors, "warnings": res.validation.warnings})
                st.stop()
            status.update(label="Bank generated", state="complete")
    except BankFolderError as e:
        st.error(str(e))
        st.stop()
    except LLMError as e:
        st.error("Model output was malformed during bank generation.")
        st.caption(str(e))
        st.stop()

    st.success(f"Generated bank `{res.bank_folder_name}`")
    st.json(
        {
            "bank_folder_name": res.bank_folder_name,
            "vector_records": res.vector_records,
            "evidence_claims": len(res.index.evidence_claims) if res.index else 0,
        }
    )
    st.info("Next: open the “Tailor Resume” page in the sidebar and select this bank.")
