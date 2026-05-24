from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from app.bank_generator.folder_manager import get_bank_paths
from app.config import DEFAULT_CONFIG
from app.llm.factory import build_llm_provider
from app.rag.ingest import ingest_experience_bank


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest an existing EXPERIENCE_BANK into the vector store.")
    ap.add_argument("--bank-folder-name", required=True)
    ap.add_argument("--ollama-url", default=DEFAULT_CONFIG.ollama_base_url)
    ap.add_argument("--model", default=DEFAULT_CONFIG.ollama_model)
    args = ap.parse_args()

    cfg = DEFAULT_CONFIG
    paths = get_bank_paths(Path(cfg.data_root), args.bank_folder_name)
    if cfg.llm_provider == "ollama":
        cfg = replace(cfg, ollama_base_url=args.ollama_url, ollama_model=args.model)
    llm = build_llm_provider(cfg)
    n, warnings = ingest_experience_bank(
        bank_folder_name=paths.bank_folder_name,
        experience_bank_dir=paths.experience_bank_dir,
        vector_store_dir=paths.vector_store_dir,
        llm=llm,
    )
    for w in warnings:
        print(f"[warn] {w}")
    print(f"Ingested {n} chunks into {paths.vector_store_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
