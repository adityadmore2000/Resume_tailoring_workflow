from __future__ import annotations

import argparse
from pathlib import Path

from app.bank_generator.folder_manager import get_bank_paths
from app.config import DEFAULT_CONFIG
from app.llm import OllamaClient
from app.rag.ingest import ingest_experience_bank


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest an existing EXPERIENCE_BANK into the vector store.")
    ap.add_argument("--bank-folder-name", required=True)
    ap.add_argument("--ollama-url", default=DEFAULT_CONFIG.ollama_base_url)
    ap.add_argument("--model", default=DEFAULT_CONFIG.ollama_model)
    args = ap.parse_args()

    paths = get_bank_paths(Path(DEFAULT_CONFIG.data_root), args.bank_folder_name)
    llm = OllamaClient(base_url=args.ollama_url, model=args.model)
    n, warnings = ingest_experience_bank(
        bank_folder_name=paths.bank_folder_name,
        experience_bank_dir=paths.experience_bank_dir,
        vector_store_dir=paths.vector_store_dir,
        llm=llm,
        embedding_model=DEFAULT_CONFIG.ollama_embedding_model,
    )
    for w in warnings:
        print(f"[warn] {w}")
    print(f"Ingested {n} chunks into {paths.vector_store_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

