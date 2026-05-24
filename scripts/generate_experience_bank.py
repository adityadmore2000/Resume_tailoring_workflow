from __future__ import annotations

import argparse
from pathlib import Path

from app.config import DEFAULT_CONFIG
from app.llm import OllamaClient
from app.bank_generator.bank_builder import generate_experience_bank


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate an EXPERIENCE_BANK from a master resume.")
    ap.add_argument("--resume-path", required=True)
    ap.add_argument("--bank-folder-name", required=True)
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing bank folder (default: false).")
    ap.add_argument("--ollama-url", default=DEFAULT_CONFIG.ollama_base_url)
    ap.add_argument("--model", default=DEFAULT_CONFIG.ollama_model)
    args = ap.parse_args()

    resume_tex = Path(args.resume_path).read_text(encoding="utf-8", errors="replace")
    llm = OllamaClient(base_url=args.ollama_url, model=args.model)
    res = generate_experience_bank(
        resume_tex=resume_tex,
        bank_folder_name=args.bank_folder_name,
        llm=llm,
        overwrite=args.overwrite,
    )
    if res.messages:
        for m in res.messages:
            print(f"[info] {m}")
    if not res.validation.ok:
        for e in res.validation.errors:
            print(f"[error] {e}")
        return 2
    print(f"Generated bank: {res.bank_folder_name} (vector records: {res.vector_records})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

