from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.bank_generator.folder_manager import get_bank_paths
from app.config import DEFAULT_CONFIG
from app.generated_resumes.latex_compiler import LatexCompileError, compile_resume_latex
from app.generated_resumes.resume_store import init_generated_resume, new_resume_id
from app.llm.factory import build_llm_provider
from app.rag.retriever import retrieve
from app.tailoring.evidence_verifier import verify_retrieved_evidence
from app.tailoring.jd_parser import parse_jd
from app.tailoring.resume_assembler import assemble_from_bank, load_bank_index
from app.tasks.task_progress import TASKS


class TailorError(ValueError):
    pass


@dataclass(frozen=True)
class TailorResult:
    bank_folder_name: str
    resume_id: str
    messages: list[str]


def tailor_resume_from_bank(*, bank_folder_name: str, jd_text: str, task_id: str | None = None) -> TailorResult:
    if not bank_folder_name.strip():
        raise TailorError("bank_name is required")
    if not jd_text.strip():
        raise TailorError("jd_text is required")

    cfg = DEFAULT_CONFIG
    llm = build_llm_provider(cfg)

    paths = get_bank_paths(Path(cfg.data_root), bank_folder_name)
    if not paths.experience_bank_dir.exists():
        raise TailorError("Bank not found")

    bank_index = load_bank_index(paths.experience_bank_dir)
    if task_id:
        TASKS.advance(task_id=task_id, step_id="resume_parsed")

    messages: list[str] = []
    jd_struct = parse_jd(jd_text, llm)
    if task_id:
        TASKS.advance(task_id=task_id, step_id="jd_analyzed")

    chunks = retrieve(
        query=jd_text,
        bank_folder_name=paths.bank_folder_name,
        llm=llm,
        top_k=12,
    )

    retrieved_eids: list[str] = []
    for c in chunks:
        eids = c.metadata.get("evidence_ids")
        if isinstance(eids, list):
            retrieved_eids.extend([str(x) for x in eids])
    retrieved_eids = list(dict.fromkeys(retrieved_eids))
    if not retrieved_eids:
        messages.append("No evidence_ids found in retrieved chunks; falling back to first 80 evidence claims.")
        retrieved_eids = [e.evidence_id for e in bank_index.evidence_claims[:80]]

    verified, evidence_map = verify_retrieved_evidence(jd=jd_struct, bank_index=bank_index, retrieved_evidence_ids=retrieved_eids)
    if task_id:
        TASKS.advance(task_id=task_id, step_id="experience_matched")

    assembled = assemble_from_bank(
        bank_dir=paths.experience_bank_dir,
        bank_index=bank_index,
        verified_evidence=verified,
        jd=jd_struct,
    )
    if task_id:
        TASKS.advance(task_id=task_id, step_id="content_tailored")
    if assembled.messages:
        messages.extend(assembled.messages)

    resume_id = new_resume_id()

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
        traceability={"items": trace_items, "evidence_map": evidence_map.model_dump()},
    )

    try:
        compile_resume_latex(paths=gen_paths)
    except LatexCompileError as e:
        messages.append(str(e))

    if task_id:
        TASKS.advance(task_id=task_id, step_id="finalized")
        TASKS.set_result(task_id=task_id, result={"bank_folder_name": paths.bank_folder_name, "resume_id": resume_id, "messages": messages})
        TASKS.complete(task_id=task_id)
    return TailorResult(bank_folder_name=paths.bank_folder_name, resume_id=resume_id, messages=messages)
