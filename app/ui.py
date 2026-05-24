from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

# Allow running via `streamlit run app/ui.py` (Streamlit sets sys.path[0] to `app/`,
# which would otherwise shadow the top-level `app` package).
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.config import DEFAULT_CONFIG
from app.latex_rebuilder import rebuild_latex
from app.llm import LLMError, OllamaClient
from app.parser import parse_latex_resume
from app.pipeline import run_pipeline
from app.schemas import SuggestionStatus


st.set_page_config(page_title="Controlled Resume Tailoring (Local LLM)", layout="wide")


def _get_llm() -> OllamaClient:
    base_url = st.session_state.get("ollama_base_url", DEFAULT_CONFIG.ollama_base_url)
    model = st.session_state.get("ollama_model", DEFAULT_CONFIG.ollama_model)
    return OllamaClient(base_url=base_url, model=model)


def _init_state() -> None:
    st.session_state.setdefault("jd_text", "")
    st.session_state.setdefault("resume_tex", "")
    st.session_state.setdefault("pipeline_result", None)
    st.session_state.setdefault("parsed_resume", None)
    st.session_state.setdefault("final_tex", None)
    st.session_state.setdefault("evaluation_after_approvals", None)
    st.session_state.setdefault("ollama_base_url", DEFAULT_CONFIG.ollama_base_url)
    st.session_state.setdefault("ollama_model", DEFAULT_CONFIG.ollama_model)


_init_state()

st.title("Controlled Resume Tailoring (Local LLM)")
st.caption("Resume is source of truth • JD is relevance signal • LLM is controlled editor • User approval required")

with st.sidebar:
    st.subheader("LLM Settings")
    st.session_state.ollama_base_url = st.text_input("Ollama base URL", value=st.session_state.ollama_base_url)
    st.session_state.ollama_model = st.text_input("Ollama model", value=st.session_state.ollama_model)
    st.caption("If you see “model not found”, run `ollama list` and `ollama pull <model>`.")

col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Job Description")
    jd_upload = st.file_uploader("Upload JD (.txt)", type=["txt"], key="jd_upload")
    if jd_upload is not None:
        st.session_state.jd_text = jd_upload.read().decode("utf-8", errors="replace")
    st.session_state.jd_text = st.text_area("Paste JD", value=st.session_state.jd_text, height=260)

with col_b:
    st.subheader("Master LaTeX Resume")
    resume_upload = st.file_uploader("Upload resume (.tex)", type=["tex"], key="resume_upload")
    if resume_upload is not None:
        st.session_state.resume_tex = resume_upload.read().decode("utf-8", errors="replace")
    st.session_state.resume_tex = st.text_area("Paste LaTeX resume", value=st.session_state.resume_tex, height=260)

run = st.button("Run tailoring pipeline", type="primary", use_container_width=True)

if run:
    if not st.session_state.jd_text.strip() or not st.session_state.resume_tex.strip():
        st.error("Provide both a job description and a LaTeX resume.")
    else:
        llm = _get_llm()
        try:
            # Upfront validation (non-blocking warnings where possible).
            resume_tex = st.session_state.resume_tex
            jd_text = st.session_state.jd_text

            if "\\" not in resume_tex:
                st.warning("Resume input does not look like LaTeX (no backslashes found). It will be preserved unchanged.")
            if "\\documentclass" not in resume_tex and "\\begin{document}" not in resume_tex:
                st.warning("Resume LaTeX is missing \\documentclass or \\begin{document}. Parsing may be partial; content will be preserved unchanged when uncertain.")

            parsed = parse_latex_resume(resume_tex)
            if parsed.warnings:
                for w in parsed.warnings:
                    st.warning(w)

            result = run_pipeline(jd_text=jd_text, resume_tex=resume_tex, llm=llm)
        except LLMError as e:
            st.error("The model returned an unexpected format. The system attempted to normalize/repair it, but couldn’t proceed for this step.")
            st.caption(str(e))
            st.stop()
        except Exception as e:
            st.error("Unexpected error while running the pipeline.")
            st.caption(str(e))
            st.stop()
        st.session_state.pipeline_result = result
        st.session_state.parsed_resume = parsed
        st.session_state.final_tex = None
        st.success("Pipeline completed. Review suggestions below.")

result = st.session_state.pipeline_result
parsed_resume = st.session_state.parsed_resume

if result is not None:
    if result.change_report.messages:
        st.subheader("System messages")
        for m in result.change_report.messages:
            st.info(m)
    st.divider()
    left, right = st.columns([1, 1])

    with left:
        st.subheader("Artifacts (read-only)")
        st.json(result.artifacts.jd_analysis.model_dump())
        st.json({"evidence_items": [i.model_dump() for i in result.artifacts.evidence_map.items[:50]]})

    with right:
        st.subheader("Recruiter-style Evaluation (baseline)")
        if result.evaluation_report is None:
            st.info("Evaluator disabled or failed.")
        else:
            st.json(result.evaluation_report.model_dump())

    st.divider()
    st.subheader("Review & Approve Changes (no auto-apply)")

    suggestions = result.change_report.suggestions
    approvals = []
    for i, s in enumerate(suggestions):
        with st.expander(f"{i+1}. {s.bullet_id} • {s.action.value} • {s.status.value}", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Original**")
                st.code(s.original_latex or "", language="latex")
            with c2:
                st.markdown("**Suggested**")
                st.code(s.suggested_latex if s.suggested_latex is not None else "(kept)", language="latex")

            st.markdown(f"**Reason:** {s.reason}")
            if s.flags:
                st.markdown("**Validation flags:**")
                st.json([f.model_dump() for f in s.flags])
            if s.status == SuggestionStatus.rejected:
                st.error(s.rejection_reason or "Rejected by verifier.")

            can_approve = s.suggested_latex is not None and s.status != SuggestionStatus.rejected
            approve_key = f"approve_{s.bullet_id}"
            default = False
            approved = st.checkbox("Approve this change", value=default, disabled=not can_approve, key=approve_key)
            approvals.append((s.bullet_id, approved))

    if st.button("Generate final LaTeX from approved changes", use_container_width=True):
        # Copy to avoid mutating baseline result in-place.
        approved_ids = {bid for bid, ok in approvals if ok}
        updated = result.change_report.model_copy(deep=True)
        for s in updated.suggestions:
            if s.bullet_id in approved_ids and s.suggested_latex is not None and s.status != SuggestionStatus.rejected:
                s.status = SuggestionStatus.approved
            else:
                s.status = SuggestionStatus.rejected if s.status == SuggestionStatus.rejected else SuggestionStatus.pending
        final_tex = rebuild_latex(parsed_resume, updated.suggestions)
        st.session_state.final_tex = final_tex
        st.success("Final LaTeX generated from approved changes only.")

    if st.session_state.final_tex:
        st.divider()
        st.subheader("Final LaTeX (approved changes only)")
        st.code(st.session_state.final_tex, language="latex")
        st.download_button("Download tailored .tex", data=st.session_state.final_tex, file_name="tailored_resume.tex")

        st.subheader("Change report (JSON)")
        st.download_button(
            "Download change_report.json",
            data=json.dumps(result.change_report.model_dump(), indent=2, ensure_ascii=False),
            file_name="change_report.json",
        )
