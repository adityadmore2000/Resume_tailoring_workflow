# System Design: Postgres Resume Tree + Qdrant resume_nodes Retrieval

## What problem this solves
Tailoring a resume for different job descriptions often requires repeated manual edits: rephrasing bullets, emphasizing the most relevant experience, and avoiding low-signal content. Typical “AI resume rewriters” can:
- hallucinate tools/skills you don’t have
- invent metrics and impact
- break LaTeX formatting
- spam keywords and hurt readability
- rewrite sections you didn’t intend to change

This system is built to be conservative and inspectable by using a **stored resume tree** as the source of truth and a **scoped semantic index** for retrieval.

## Core runtime architecture (only supported path)
At runtime, the system uses:
- **Postgres** tables:
  - `resumes` (one row per bank/resume; stores source resume text in `metadata`)
  - `resume_nodes` (the parsed resume as a tree: sections → items → details)
- **Qdrant**:
  - one collection for **resume_nodes embeddings** (points keyed by `node_id`, filtered by `resume_id`)
- **Generated artifacts**:
  - `data/generated_resumes/<bank_slug>/<resume_id>/...` (`resume.tex`, optional `resume.pdf`, `traceability.json`, logs)

There is no supported runtime path that reads from `data/experience_bank/`, `banks_registry.json`, or `experience_bank_index.json`.

## High-level flow
### 1) Bank creation (resume ingestion)
Goal: parse a master resume into a durable, queryable structure.

- Input: LaTeX or plain text resume
- Output:
  - Postgres `resumes` row (includes `metadata.source_resume_tex` when LaTeX)
  - Postgres `resume_nodes` tree
    - structural nodes: `resume_root`, `section`, `item`
    - content nodes: `detail` (typically marked `metadata.searchable=true`)

### 2) Tailoring
Goal: tailor a resume using only the stored resume tree + scoped retrieval.

- JD text is parsed into a structured shape (LLM extractor).
- Qdrant retrieval runs against the **resume_nodes index**, scoped by `resume_id`.
- The system builds hierarchy-aware context from retrieved node ids (Section → Item → Detail).
- Targeted bullets are rewritten using:
  - the JD keywords
  - allowed tools/skills extracted from the resume tree metadata
  - immutable spans stored in `resume_nodes.metadata.immutable_fields` (for safe LaTeX replacement)
- Outputs are saved under `data/generated_resumes/...` with `traceability.json` describing what matched and why.

## Why the tree is the source of truth
- The resume tree is stored in Postgres and is independent of local disk “bank folders”.
- Qdrant is an index only (cacheable/replaceable); it is not trusted state.
- Tailoring never silently falls back to legacy local bank files.

## Failure handling (conservative defaults)
- If Qdrant is unavailable, the backend fails fast at startup (Qdrant is required for semantic retrieval).
- If rewriting fails or fails validation, the system keeps the original bullet.
- If LaTeX compilation fails, the tailored `.tex` and traceability artifacts are still persisted.

## Human review workflow
The supported product UI is **Next.js** (separate frontend repo) backed by the FastAPI backend:
- Create bank → Tailor → Review generated resume artifacts (LaTeX/PDF/traceability).

