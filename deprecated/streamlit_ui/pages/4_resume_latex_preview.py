from __future__ import annotations

import base64
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.generated_resumes.latex_compiler import LatexCompileError, compile_resume_latex  # noqa: E402
from app.generated_resumes.resume_store import (  # noqa: E402
    GeneratedResumePaths,
    ResumeStoreError,
    get_generated_resume_paths,
    read_markdown,
    read_latex,
    read_metadata,
    read_text,
    read_traceability,
    save_latex,
)
from app.ui.components.top_nav import render_top_nav  # noqa: E402


st.title("Resume Workspace")
st.caption("Step 4 of 4 — Review, edit LaTeX, recompile, and export a recruiter-ready PDF.")
render_top_nav(active="Resume Workspace")

with st.container(border=True):
    st.subheader("Step 4 of 4 — Review & Export")
    st.markdown(
        "\n".join(
            [
                "Edit LaTeX, review traceability, recompile PDF, and export the final recruiter-ready resume.",
                "",
                "**What to know**",
                "- **PDF Preview** is read-only.",
                "- **LaTeX Source** is editable and recompilable.",
                "- **Traceability** maps generated bullets back to source evidence so you can audit edits confidently.",
            ]
        )
    )
    with st.expander("How this works"):
        st.markdown(
            "\n".join(
                [
                    "1. The workspace loads a previously generated `resume_id`.",
                    "2. You edit LaTeX, then recompile to update the PDF preview.",
                    "3. Traceability stays available as an audit trail from bullets → evidence claims.",
                ]
            )
        )


def _pdf_iframe(pdf_bytes: bytes, *, height: int = 900) -> None:
    b64 = base64.b64encode(pdf_bytes).decode("ascii")
    html = f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="{height}px"></iframe>'
    st.components.v1.html(html, height=height + 20, scrolling=True)


def _load_paths() -> GeneratedResumePaths | None:
    # Prefer query param (resume_id-based route), fallback to session_state.
    qp = st.query_params
    resume_id = qp.get("resume_id") or st.session_state.get("resume_id")
    bank = st.session_state.get("bank_folder_name")
    if not resume_id:
        return None

    # If bank is missing (e.g., opened from URL), attempt to resolve by scanning generated_resumes.
    if not bank:
        root = (Path("data") / "generated_resumes").resolve()
        if root.exists():
            for b in root.iterdir():
                if not b.is_dir():
                    continue
                if (b / str(resume_id)).exists():
                    bank = b.name
                    st.session_state["bank_folder_name"] = bank
                    break
    if not bank:
        return None
    try:
        st.session_state["resume_id"] = str(resume_id)
        return get_generated_resume_paths(bank_folder_name=str(bank), resume_id=str(resume_id))
    except ResumeStoreError:
        return None


paths = _load_paths()

if paths is None:
    st.info("No resume_id provided. Generate a tailored resume first (Tailor Resume page).")
    st.stop()

with st.expander("Resume context (technical)"):
    st.write({"bank_folder_name": paths.bank_folder_name, "resume_id": paths.resume_id})
    meta = read_metadata(paths)
    if meta:
        st.caption("Metadata")
        st.json(meta)

latex_current, _ = read_latex(paths)
st.session_state.setdefault("latex_editor_value", latex_current)

toolbar = st.columns([1, 1, 1, 2])
save_clicked = toolbar[0].button("Save", use_container_width=True)
compile_clicked = toolbar[1].button("Recompile", type="primary", use_container_width=True)
export_clicked = toolbar[2].button("Export PDF", use_container_width=True)
status_placeholder = toolbar[3].empty()

tabs = st.tabs(["PDF Preview", "LaTeX Source", "Tailored Markdown", "Tailored Text", "Traceability", "Compile Logs"])

with tabs[0]:
    st.subheader("PDF Preview (read-only)")
    if paths.pdf_path.exists():
        try:
            _pdf_iframe(paths.pdf_path.read_bytes(), height=860)
        except Exception:
            st.warning("Failed to render PDF preview. You can still export the PDF if it exists.")
    else:
        st.info("No compiled PDF yet. Click Recompile after editing LaTeX.")

with tabs[1]:
    st.subheader("LaTeX Source (editable)")
    st.caption("Tip: Make small edits, then click Recompile. Compilation keeps the last successful PDF if an error occurs.")
    try:
        from streamlit_ace import st_ace  # type: ignore

        code = st_ace(
            value=st.session_state.latex_editor_value,
            language="latex",
            theme="chrome",
            key="latex_ace",
            height=860,
            font_size=13,
            tab_size=2,
            wrap=True,
            show_gutter=True,
            show_print_margin=False,
            auto_update=True,
        )
    except Exception:
        st.caption("Install `streamlit-ace` for a better editor (`pip install streamlit-ace`).")
        code = st.text_area("LaTeX source", value=st.session_state.latex_editor_value, height=860)
    st.session_state.latex_editor_value = code or ""

with tabs[2]:
    st.subheader("Tailored Markdown")
    md = read_markdown(paths)
    st.code(md or "(not available)", language="markdown")
    st.download_button("Download .md", data=md or "", file_name=f"{paths.resume_id}.md")

with tabs[3]:
    st.subheader("Tailored Text")
    txt = read_text(paths)
    st.code(txt or "(not available)", language="text")
    st.download_button("Download .txt", data=txt or "", file_name=f"{paths.resume_id}.txt")

with tabs[4]:
    st.subheader("Traceability")
    st.caption("If a bullet doesn't map to evidence, it should be treated as unverified and removed/edited.")
    st.json(read_traceability(paths))

with tabs[5]:
    st.subheader("Compile Logs")
    if paths.log_path.exists():
        st.code(paths.log_path.read_text(encoding="utf-8", errors="replace")[-12000:])
    else:
        st.caption("No compile log yet.")


def _set_status(text: str) -> None:
    status_placeholder.write(text)


if save_clicked:
    save_latex(paths, st.session_state.latex_editor_value)
    _set_status(f"Saved at {datetime.now().strftime('%H:%M:%S')}")
    st.toast("Saved")

if compile_clicked:
    # Always save before compile.
    save_latex(paths, st.session_state.latex_editor_value)
    try:
        res = compile_resume_latex(paths=paths)
    except LatexCompileError as e:
        _set_status("Compile error: compiler not found")
        st.error(str(e))
        # Refresh preview/log panel without clearing editor state.
        st.rerun()
    else:
        if res.status == "success":
            _set_status(f"Compiled successfully at {res.compiled_at}")
            st.toast("Compiled")
            st.rerun()
        else:
            _set_status(f"Compile failed at {res.compiled_at} (showing last successful preview if available)")
            st.error("Compilation failed. Fix errors and recompile. (Last successful PDF preview is kept if it exists.)")
            st.rerun()

if export_clicked:
    if not paths.pdf_path.exists():
        st.error("No PDF to export yet. Compile first.")
    else:
        st.download_button(
            "Download compiled PDF",
            data=paths.pdf_path.read_bytes(),
            file_name=f"{paths.bank_folder_name}_{paths.resume_id}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

st.divider()
st.markdown("### Next step")
post = st.columns([1, 1, 2])
post[0].page_link("ui/pages/2_tailor_resume.py", label="Create Another Tailored Resume", icon="✍️", use_container_width=True)
post[1].page_link("ui/pages/3_preview_experience_bank.py", label="Review Experience Bank", icon="🔎", use_container_width=True)
