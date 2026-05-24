from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.bank_generator.bank_builder import list_banks  # noqa: E402
from app.bank_generator.folder_manager import get_bank_paths  # noqa: E402
from app.config import DEFAULT_CONFIG  # noqa: E402
from app.llm import LLMError  # noqa: E402
from app.llm.factory import build_llm_provider  # noqa: E402
from app.rag.retriever import retrieve  # noqa: E402
from app.tailoring.evidence_verifier import verify_retrieved_evidence  # noqa: E402
from app.tailoring.jd_parser import parse_jd  # noqa: E402
from app.tailoring.resume_assembler import assemble_from_bank, load_bank_index  # noqa: E402
from app.ui.api.banks_api import get_bank_options  # noqa: E402
from app.generated_resumes.resume_store import init_generated_resume, new_resume_id  # noqa: E402
from app.generated_resumes.latex_compiler import LatexCompileError, compile_resume_latex  # noqa: E402


st.title("Tailor Resume (from Experience Bank)")
st.caption("No resume upload here. Tailoring uses only the selected bank’s KB + vector store.")

st.session_state.setdefault("tailor_selected_bank", "")
st.session_state.setdefault("tailor_jd_text", "")
st.session_state.setdefault("tailor_last_error", "")
st.session_state.setdefault("tailor_last_resume_id", "")

banks = list_banks()
bank_names = get_bank_options()

col_actions = st.columns([1, 1, 3])
clear_clicked = col_actions[0].button("Clear", use_container_width=True)
if clear_clicked:
    # Reset UI state only; never delete generated artifacts.
    for k in [
        "tailor_selected_bank",
        "tailor_jd_text",
        "tailor_last_error",
        "tailor_last_resume_id",
        "tailor_last_evidence_map",
        "tailor_last_chunks",
    ]:
        if k in st.session_state:
            del st.session_state[k]
    st.session_state["tailor_selected_bank"] = ""
    st.session_state["tailor_jd_text"] = ""
    st.toast("Cleared form state")
    st.rerun()

selected = st.selectbox("Select bank", options=[""] + bank_names, key="tailor_selected_bank", index=0)
if selected:
    meta = next((b for b in banks if b.bank_folder_name == selected), None)
    if meta:
        st.json(meta.model_dump())

jd_upload = st.file_uploader("Upload Job Description (.txt/.md)", type=["txt", "md"], key="tailor_jd_upload")
if jd_upload is not None:
    st.session_state["tailor_jd_text"] = jd_upload.read().decode("utf-8", errors="replace")
jd_text = st.text_area("Or paste JD", key="tailor_jd_text", height=240)

run = st.button("Tailor using selected bank", type="primary", use_container_width=True)
st.page_link(
    "ui/pages/4_resume_latex_preview.py",
    label="Open Resume LaTeX Preview",
    icon="🧾",
    use_container_width=True,
    disabled=not bool(st.session_state.get("resume_id")),
)

if run:
    try:
        if not selected:
            st.error("Select a bank first.")
            st.stop()
        if not jd_text.strip():
            st.error("Job description is required.")
            st.stop()

        cfg = DEFAULT_CONFIG
        if cfg.llm_provider == "ollama":
            cfg = replace(
                cfg,
                ollama_base_url=st.session_state.ollama_base_url,
                ollama_model=st.session_state.ollama_model,
                ollama_embedding_model=st.session_state.ollama_embed_model,
            )
        llm = build_llm_provider(cfg)
        paths = get_bank_paths(Path(cfg.data_root), selected)
        bank_index = load_bank_index(paths.experience_bank_dir)

        with st.status("Tailoring from KB…", expanded=True) as status:
            st.write("Parsing JD → structured requirements")
            jd_struct = parse_jd(jd_text, llm)

            st.write("Retrieving evidence (hybrid)")
            chunks = retrieve(
                query=jd_text,
                bank_folder_name=paths.bank_folder_name,
                vector_store_dir=paths.vector_store_dir,
                llm=llm,
                top_k=12,
            )
            st.session_state["tailor_last_chunks"] = [{"chunk_id": c.chunk_id, "score": c.score, "metadata": c.metadata} for c in chunks]
            st.json(st.session_state["tailor_last_chunks"])

            retrieved_eids: list[str] = []
            for c in chunks:
                eids = c.metadata.get("evidence_ids")
                if isinstance(eids, list):
                    retrieved_eids.extend([str(x) for x in eids])
            retrieved_eids = list(dict.fromkeys(retrieved_eids))
            if not retrieved_eids:
                st.warning("No evidence_ids found in retrieved chunks; falling back to first 80 evidence claims.")
                retrieved_eids = [e.evidence_id for e in bank_index.evidence_claims[:80]]

            st.write("Evidence verification (deterministic)")
            verified, evidence_map = verify_retrieved_evidence(jd=jd_struct, bank_index=bank_index, retrieved_evidence_ids=retrieved_eids)
            st.session_state["tailor_last_evidence_map"] = evidence_map.model_dump()
            st.json(st.session_state["tailor_last_evidence_map"])

        st.write("Resume assembly (evidence-grounded)")
        assembled = assemble_from_bank(
            bank_dir=paths.experience_bank_dir,
            bank_index=bank_index,
            verified_evidence=verified,
            jd=jd_struct,
        )
        if assembled.messages:
            for m in assembled.messages:
                st.info(m)

        st.write("Saving generated LaTeX + compiling PDF")
        resume_id = new_resume_id()
        # Traceability: evidence-grounded bullets only (no evidence_id => no bullet).
        claim_by_id = {c.evidence_id: c for c in bank_index.evidence_claims}
        trace_items = []
        for eid in assembled.used_evidence_ids:
            c = claim_by_id.get(eid)
            if not c:
                continue
            trace_items.append(
                {
                    "generated_bullet": c.claim_text,
                    "evidence_ids": [eid],
                    "source_section": c.source_section,
                    "source_text": c.source_text,
                }
            )
        gen_paths = init_generated_resume(
            bank_folder_name=paths.bank_folder_name,
            resume_id=resume_id,
            latex=assembled.latex,
            markdown=assembled.markdown,
            text=assembled.text,
            traceability={"items": trace_items},
        )
        try:
            compile_resume_latex(paths=gen_paths)
        except LatexCompileError as e:
            st.warning(str(e))

        st.session_state["bank_folder_name"] = paths.bank_folder_name
        st.session_state["resume_id"] = resume_id
        st.session_state["tailor_last_resume_id"] = resume_id

        status.update(label="Tailored resume assembled", state="complete")
    except Exception as e:
        st.error("Tailoring failed due to an unexpected format or validation issue. The system kept your bank unchanged.")
        st.exception(e)
        st.session_state["tailor_last_error"] = str(e)
        st.stop()

    # Success flow: navigate directly into the review workspace.
    st.switch_page("ui/pages/4_resume_latex_preview.py", query_params={"resume_id": resume_id})

# Persisted state preview (does not clear after submit)
if st.session_state.get("tailor_last_resume_id"):
    st.info(f"Last generated resume_id: {st.session_state['tailor_last_resume_id']}")
if st.session_state.get("tailor_last_error"):
    st.error(st.session_state["tailor_last_error"])
