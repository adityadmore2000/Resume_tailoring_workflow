# Local LLM Resume Tailoring (Controlled Pipeline)

This project scaffolds a **local-LLM-powered resume tailoring system** designed as a **controlled, multi-step pipeline** (not a one-prompt rewriter).

Core principle:
- **Resume is the source of truth**
- **Job description (JD) is only a relevance signal**
- **LLM is a controlled editor**
- **All risky changes are validated and require explicit user approval**

## Features (MVP)
- LaTeX resume parsing into structured JSON (stable bullet IDs; text spans tracked)
- JD analysis via Ollama → structured JSON
- Evidence mapping (JD requirements → only resume-supported evidence)
- JSON-only rewrite planning (no content rewriting at this stage)
- Safe rewrite engine (only rewrites approved bullets)
- Deterministic verifier (hallucinations/metrics/LaTeX/keyword stuffing/length/section checks)
- LaTeX rebuilder (surgical replacements; no full regeneration)
- Separate recruiter-style evaluation stage (local LLM)
- CLI + Streamlit human-in-the-loop review UI
- Optional: schema-driven `EXPERIENCE_BANK` generation + per-bank RAG indexing

## Setup
1. Install Python dependencies:
   - `python -m pip install -r requirements.txt`
2. Install and run Ollama:
   - Install Ollama (see Ollama docs)
   - Pull a model (the default config expects a smaller model): `ollama pull llama3.2:3b`
   - Ensure Ollama is running on `http://localhost:11434`

Configuration defaults live in `app/config.py`.

### Ollama model requirements
This project does not require a specific model family, but it does require that:
- the model is installed in Ollama (`ollama list` shows it)
- it can follow “JSON-only” instructions reasonably well (for the extraction/planning/evaluation stages)

Defaults:
- `ollama_model = llama3.2:3b` (chosen to be more likely to work on ~4GB VRAM machines)

If you have a different model installed, use:
- CLI: `--model <your_model>`
- UI: set the model in the sidebar

Suggested models for ~4GB VRAM (pick one you can run reliably):
- `llama3.2:3b`
- `qwen2.5:3b`
- `phi3:mini`
- `gemma2:2b`

## CLI usage
Example:
- `python -m app.main --resume examples/sample_resume.tex --jd examples/sample_jd.txt --out outputs/tailored_resume.tex`

Outputs:
- Tailored LaTeX at `--out`
- Reports next to it: `*.change_report.json`, `*.evaluation.json`, and `*.artifacts.json`

Safety note:
- By default, **no suggestions are auto-approved**, so `--out` will match your input resume until you approve changes in the UI.
- If you explicitly want non-interactive application of verifier-passing suggestions, pass `--auto-approve-safe` (not recommended for real use).

Legacy note:
- `python -m app.main ...` runs the older “edit this LaTeX resume” pipeline (still kept for fallback/testing).
- The recommended product flow is: **generate an EXPERIENCE_BANK once**, then **tailor from the bank** (no resume upload in tailoring).

## UI usage (MVP)
- `streamlit run app/ui.py`

Workflow:
1. Create an `EXPERIENCE_BANK` from a master resume (upload once)
2. Tailor a resume by selecting a bank + providing a JD (no resume upload during tailoring)

## Experience banks (optional)
Generate an evidence-grounded knowledge base from a master resume (stored per bank folder):
- Source upload snapshot: `data/uploads/<bank>/resume.tex`
- Knowledge base: `data/experience_bank/<bank>/...`
- Per-bank vector store: `data/vector_store/<bank>/index.jsonl`
- Registry: `data/experience_bank/banks_registry.json`

CLI scripts:
- Generate: `python scripts/generate_experience_bank.py --resume-path main.tex --bank-folder-name "Aditya AI Master Resume"`
- List: `python scripts/list_experience_banks.py`
- Re-ingest vectors: `python scripts/ingest_experience_bank.py --bank-folder-name <bank>`
- Tailor using a selected bank (no resume input): `python scripts/tailor_resume.py --jd-path <jd.txt> --bank-folder-name <bank> --out outputs/tailored.tex --format latex`

## Docs
- `docs/SYSTEM_DESIGN.md`
- `docs/TECHNICAL_DOCUMENTATION.md`

## Notes / Limitations
- LaTeX parsing is template-agnostic but still heuristic (regex-based). It aims to be safe, not perfect.
- Deterministic verifiers are conservative: when in doubt, the system keeps the original bullet.
- No LangChain/LangGraph in MVP; orchestration is plain Python functions so a graph layer can be added later.
