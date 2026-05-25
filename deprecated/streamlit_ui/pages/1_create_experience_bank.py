from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.bank_generator.bank_builder import generate_experience_bank  # noqa: E402
from app.bank_generator.folder_manager import BankFolderError, get_bank_paths  # noqa: E402
from app.config import DEFAULT_CONFIG  # noqa: E402
from app.llm import LLMError  # noqa: E402
from app.llm.factory import build_llm_provider  # noqa: E402
from app.resume_parser.section_detector import looks_like_latex  # noqa: E402
from app.ui.components.top_nav import render_top_nav  # noqa: E402


st.title("Create Experience Bank")
st.caption("Upload a master resume once → generate an evidence-grounded KB + per-bank vector index.")
render_top_nav(active="Create Experience Bank")

with st.container(border=True):
    st.subheader("Step 1 of 4 — Create Experience Bank")
    st.markdown(
        "\n".join(
            [
                "This page converts your **master resume** into a reusable **Experience Bank** used for future tailoring.",
                "",
                "**Input guidance**",
                "- Upload a master resume (LaTeX or text).",
                "- Use a stable bank name (you’ll reuse it for every job).",
                "- Supported formats: `.tex`, `.txt`, `.pdf` (PDF is future-ready; MVP expects `.tex`/`.txt`).",
                "",
                "Hints:",
                "- The system does **not** re-read resumes during tailoring.",
                "- Experience Banks become the **source-of-truth** for resume generation.",
            ]
        )
    )
    st.popover("What is an Experience Bank?").markdown(
        "\n".join(
            [
                "An Experience Bank is a structured knowledge base extracted from your master resume.",
                "Tailoring retrieves only evidence from the bank (plus its vector index), so you don’t keep uploading resumes.",
            ]
        )
    )
    with st.expander("How this works"):
        st.markdown(
            "\n".join(
                [
                    "1. The resume is parsed into sections and bullets.",
                    "2. Atomic evidence claims are extracted and validated.",
                    "3. A knowledge base (KB) is written as human-readable pages.",
                    "4. The KB is embedded into a per-bank vector store for semantic retrieval.",
                ]
            )
        )

bank_name = st.text_input("Bank folder name (required)", placeholder="e.g., aditya_ai_master_resume")
st.caption("Use a stable name. You’ll select this bank during tailoring instead of re-uploading a resume.")
overwrite = st.checkbox("Overwrite existing bank (requires confirmation)", value=False)
confirm_overwrite = st.checkbox("I understand overwrite may replace an existing bank", value=False, disabled=not overwrite)

uploaded = st.file_uploader(
    "Upload master resume (.tex / .txt / .pdf)",
    type=["tex", "txt", "pdf"],
    help="Recommended: upload your master resume once. Tailoring will use the bank, not this file.",
)
resume_text = ""
source_format = "latex"
if uploaded is not None:
    if uploaded.name.endswith(".pdf"):
        st.error("PDF parsing is not supported in this MVP yet. Please upload `.tex` or `.txt` for now.")
        st.stop()
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

    try:
        cfg = DEFAULT_CONFIG
        if cfg.llm_provider == "ollama":
            cfg = replace(
                cfg,
                ollama_base_url=st.session_state.ollama_base_url,
                ollama_model=st.session_state.ollama_model,
                ollama_embedding_model=st.session_state.ollama_embed_model,
            )
        llm = build_llm_provider(cfg)
        # Pre-check existence for friendly UI.
        paths = get_bank_paths(Path(cfg.data_root), bank_name)
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
    domains = set()
    if res.index and res.index.capabilities:
        for c in res.index.capabilities:
            for d in c.domains or []:
                if isinstance(d, str) and d.strip():
                    domains.add(d.strip())
    st.json(
        {
            "bank_folder_name": res.bank_folder_name,
            "vector_chunks": res.vector_records,
            "evidence_claims": len(res.index.evidence_claims) if res.index else 0,
            "domains": sorted(domains)[:60],
        }
    )
    st.info("Experience Bank created successfully. Recommended next step: review it before tailoring.")
    next_actions = st.columns([1, 1, 2])
    next_actions[0].page_link("ui/pages/3_preview_experience_bank.py", label="Preview Experience Bank", icon="🔎", use_container_width=True)
    next_actions[1].page_link("ui/pages/2_tailor_resume.py", label="Tailor Resume", icon="✍️", use_container_width=True)
