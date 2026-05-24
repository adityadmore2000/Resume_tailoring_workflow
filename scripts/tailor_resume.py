from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from app.bank_generator.folder_manager import get_bank_paths
from app.config import DEFAULT_CONFIG
from app.llm.factory import build_llm_provider
from app.tailoring.jd_parser import parse_jd
from app.tailoring.evidence_verifier import verify_retrieved_evidence
from app.tailoring.resume_assembler import assemble_from_bank
from app.tailoring.resume_assembler import load_bank_index  # backward compat import
from app.rag.retriever import retrieve


def main() -> int:
    ap = argparse.ArgumentParser(description="Tailor a resume using a selected EXPERIENCE_BANK.")
    ap.add_argument("--jd-path", required=True)
    ap.add_argument("--bank-folder-name", required=True)
    ap.add_argument("--out", required=True, help="Output file path")
    ap.add_argument("--format", default="latex", choices=["latex", "markdown", "text"])
    ap.add_argument("--ollama-url", default=DEFAULT_CONFIG.ollama_base_url)
    ap.add_argument("--model", default=DEFAULT_CONFIG.ollama_model)
    args = ap.parse_args()

    jd = Path(args.jd_path).read_text(encoding="utf-8", errors="replace")

    cfg = DEFAULT_CONFIG
    paths = get_bank_paths(Path(cfg.data_root), args.bank_folder_name)
    bank_index = load_bank_index(paths.experience_bank_dir)

    if cfg.llm_provider == "ollama":
        cfg = replace(cfg, ollama_base_url=args.ollama_url, ollama_model=args.model)
    llm = build_llm_provider(cfg)
    jd_struct = parse_jd(jd, llm)
    retrieved = retrieve(
        query=jd,
        bank_folder_name=paths.bank_folder_name,
        vector_store_dir=paths.vector_store_dir,
        llm=llm,
        top_k=10,
    )
    # Map retrieved chunks back to evidence_ids if present in metadata; fallback to none.
    retrieved_eids: list[str] = []
    for c in retrieved:
        eids = c.metadata.get("evidence_ids")
        if isinstance(eids, list):
            retrieved_eids.extend([str(x) for x in eids])
    # If no evidence_ids present, fall back to using the first N evidence claims (conservative).
    if not retrieved_eids:
        retrieved_eids = [e.evidence_id for e in bank_index.evidence_claims[:50]]

    verified, evidence_map = verify_retrieved_evidence(jd=jd_struct, bank_index=bank_index, retrieved_evidence_ids=retrieved_eids)
    assembled = assemble_from_bank(bank_dir=paths.experience_bank_dir, bank_index=bank_index, verified_evidence=verified, jd=jd_struct)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "latex":
        out_path.write_text(assembled.latex, encoding="utf-8")
    elif args.format == "markdown":
        out_path.write_text(assembled.markdown, encoding="utf-8")
    else:
        out_path.write_text(assembled.text, encoding="utf-8")

    out_path.with_suffix(".evidence_map.json").write_text(json.dumps(evidence_map.model_dump(), indent=2), encoding="utf-8")
    out_path.with_suffix(".used_evidence_ids.json").write_text(json.dumps({"used_evidence_ids": assembled.used_evidence_ids}, indent=2), encoding="utf-8")
    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
