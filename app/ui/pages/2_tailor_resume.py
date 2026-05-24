from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.bank_generator.bank_builder import list_banks  # noqa: E402
from app.bank_generator.folder_manager import get_bank_paths  # noqa: E402
from app.config import DEFAULT_CONFIG  # noqa: E402
from app.llm import LLMError, OllamaClient  # noqa: E402
from app.rag.retriever import retrieve  # noqa: E402
from app.tailoring.evidence_verifier import verify_retrieved_evidence  # noqa: E402
from app.tailoring.jd_parser import parse_jd  # noqa: E402
from app.tailoring.resume_assembler import assemble_from_bank, load_bank_index  # noqa: E402
from app.ui.api.banks_api import get_bank_options  # noqa: E402


st.title("Tailor Resume (from Experience Bank)")
st.caption("No resume upload here. Tailoring uses only the selected bank’s KB + vector store.")

banks = list_banks()
bank_names = get_bank_options()
selected = st.selectbox("Select bank", options=[""] + bank_names, index=0)
if selected:
    meta = next((b for b in banks if b.bank_folder_name == selected), None)
    if meta:
        st.json(meta.model_dump())

jd_upload = st.file_uploader("Upload Job Description (.txt/.md)", type=["txt", "md"])
jd_text = ""
if jd_upload is not None:
    jd_text = jd_upload.read().decode("utf-8", errors="replace")
jd_text = st.text_area("Or paste JD", value=jd_text, height=240)

run = st.button("Tailor using selected bank", type="primary", use_container_width=True)

if run:
    try:
        if not selected:
            st.error("Select a bank first.")
            st.stop()
        if not jd_text.strip():
            st.error("Job description is required.")
            st.stop()

        llm = OllamaClient(base_url=st.session_state.ollama_base_url, model=st.session_state.ollama_model)
        paths = get_bank_paths(Path(DEFAULT_CONFIG.data_root), selected)
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
                embedding_model=DEFAULT_CONFIG.ollama_embedding_model,
                top_k=12,
            )
            st.json([{"chunk_id": c.chunk_id, "score": c.score, "metadata": c.metadata} for c in chunks])

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
            st.json(evidence_map.model_dump())

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

            status.update(label="Tailored resume assembled", state="complete")
    except Exception as e:
        st.error("Tailoring failed due to an unexpected format or validation issue. The system kept your bank unchanged.")
        st.exception(e)
        st.stop()

    st.subheader("Tailored LaTeX")
    st.code(assembled.latex, language="latex")
    st.download_button("Download .tex", data=assembled.latex, file_name=f"{paths.bank_folder_name}_tailored.tex")

    st.subheader("Tailored Markdown")
    st.code(assembled.markdown, language="markdown")
    st.download_button("Download .md", data=assembled.markdown, file_name=f"{paths.bank_folder_name}_tailored.md")

    st.subheader("Tailored Text")
    st.code(assembled.text, language="text")
    st.download_button("Download .txt", data=assembled.text, file_name=f"{paths.bank_folder_name}_tailored.txt")

    st.subheader("Traceability")
    st.json({"used_evidence_ids": assembled.used_evidence_ids})
    st.download_button("Download evidence_map.json", data=json.dumps(evidence_map.model_dump(), indent=2), file_name="evidence_map.json")
