# System Design: Evidence-Grounded Resume KB + Tailoring

## What problem this solves
Tailoring a resume for different job descriptions often requires repeated manual edits: rephrasing bullets, emphasizing the most relevant experience, and removing low-signal content. The risky part is that typical “AI resume rewriters” can:
- hallucinate tools/skills you don’t have
- invent metrics and impact
- break LaTeX formatting
- spam keywords and hurt readability
- rewrite random sections you did not intend to change

This system is built to solve that problem **safely** by turning your master resume into an **evidence-grounded knowledge base** first, and then tailoring from that KB using deterministic constraints (not free-form rewriting).

## Project motivation
The motivation is two-fold:
1. Make resume tailoring faster without rewriting from scratch each time.
2. Learn how production-style, controlled local-LLM systems are designed (multi-step workflows with validation), instead of relying on one giant prompt.

## Why this is not a simple chatbot or one-prompt resume writer
One large prompt tends to blend planning, editing, and evaluation into a single stochastic output. That makes it hard to:
- inspect why changes happened
- validate risky claims
- limit modifications to intended regions
- safely preserve formatting and template structure

This project explicitly separates:
- **bank creation** (resume → evidence claims → validated KB → vector index)
- **retrieval** (bank-scoped hybrid retrieval)
- **verification** (deterministic evidence verifier)
- **assembly** (deterministic resume assembler)
- **review + export** (browser LaTeX workspace + PDF compile)

## Two-phase product flow
This system is designed to be used in two phases:
1. **Experience Bank Creation** (upload master resume once)
2. **Resume Tailoring from Existing KB** (no resume upload; bank is the source of truth)

## Core design principle
- **Master resume → Experience Bank is the source of truth:** if it is not present in the bank evidence, the system does not add it.
- **JD is only a relevance signal:** it influences ranking/selection and light formatting, not factual claims.
- **Retrieval can be noisy; generation must not be:** retrieved chunks are verified deterministically before use.
- **Prefer safety over “helpfulness”:** when uncertain, keep content unchanged or omit optional sections (never invent).

## High-level architecture (two phases)
The system is split into **two distinct phases**:

### Phase 1 — Experience Bank Creation
Goal: convert a master resume into an evidence-grounded knowledge base that becomes the source of truth.

Main components:
- Resume parsing (LaTeX/text) → bullets + spans
- Atomic evidence extraction (`evidence_id`, `source_text`, `source_section`)
- Work/project grouping extraction (from LaTeX macros when available)
- Schema validation (reject unsupported shapes; enforce evidence references)
- Deterministic KB writing (markdown + JSON index)
- Per-bank vector index ingestion (RAG)
- Registry update (`banks_registry.json`)

### Phase 2 — Resume Tailoring from Existing KB
Goal: tailor a resume **without requiring the user to provide the raw resume again**.

Tailoring operates only on:
- `data/experience_bank/<bank>/...`
- Qdrant collection `resume_tailor_chunks` (scoped by `bank_folder_name`)
- `banks_registry.json`

Main components:
- JD parsing into structured requirements (LLM extractor)
- Bank-scoped semantic retrieval (Qdrant-only)
- Deterministic evidence verification (`supported/partially_supported/unsupported`)
- Resume assembly using verified evidence IDs only
- Skills categorization (recruiter-friendly categories; evidence-grounded)
- LaTeX structure preflight validation + safe auto-fix (pre-compile)
- Browser-based LaTeX workspace (edit → compile → preview → export PDF)

## Experience bank (optional) architecture
For repeated tailoring across many JDs, this project also supports generating an **EXPERIENCE_BANK**:
- A per-user/per-resume, evidence-grounded knowledge base derived from a master resume
- Stored under `data/experience_bank/<bank_folder_name>/`
- Indexed for retrieval in Qdrant (`resume_tailor_chunks`) with bank isolation via `bank_folder_name`
- Registered in `data/experience_bank/banks_registry.json`

Key principle:
**EXPERIENCE_BANK is the source of truth** (derived from the uploaded master resume once). Tailoring never reads the upload again.

## Pipeline flow (current UI)
Phase 1:
Upload master resume → parse → extract evidence → validate → write bank → ingest vectors → registry update

Phase 2:
Select bank → paste/upload JD → retrieve → verify → assemble LaTeX/Markdown/Text → save `resume_id` → open LaTeX workspace (PDF preview + export)

## Module responsibilities
### 1) Resume parsing
Responsibility:
- Parse LaTeX into a structured form (sections + bullets).
- Assign stable bullet IDs.
- Track *span positions* for each bullet content in the original LaTeX.
- Extract a conservative list of skills/tools from the Skills section.

Key safety choice:
- The LLM never sees or edits the full LaTeX document as a single blob to “regenerate”.

### 2) JD analyzer (LLM extractor)
Responsibility:
- Convert JD text into structured JSON: skills, focus areas, keywords, rejection risks.

Key safety choice:
- The analyzer is an extractor. It does not claim anything about the candidate.

### 3) Bank-scoped retrieval (RAG)
Responsibility:
- Retrieve potentially relevant KB chunks, scoped to the selected bank only.

Key safety choice:
- Retrieval is scoped per bank folder to prevent cross-bank contamination.

### 4) Evidence verification (deterministic)
Responsibility:
 - Classify whether retrieved evidence supports each JD requirement.

Key safety choice:
 - Missing evidence stays missing; it is not invented.

### 5) Resume assembly (deterministic)
Responsibility:
- Assemble a tailored resume with a fixed top-level order:
  `HEADER → SUMMARY → EXPERIENCE → PROJECTS → SKILLS → EDUCATION`
- EXPERIENCE completeness is enforced (do not drop work entries).
- Bullets are selected from verified evidence; if none match for a company, fall back to safe bullets from that entry.

Key safety choice:
- “No evidence_id = no bullet.”

### 6) LaTeX structure guard + compilation
Responsibility:
- Validate list/macro wrappers before compilation.
- Apply safe end-of-document auto-fixes if possible and log them.
- Compile in an isolated resume workspace directory (`latexmk` preferred; `pdflatex` fallback).

Key safety choice:
- No user-supplied shell commands; no shell escape; timeouts.

### 7) Browser review workspace
Responsibility:
- Provide a split view editor + PDF preview.
- Allow recompile, export PDF, and view artifacts (Markdown/Text/Traceability/Logs).

Key safety choice:
- Compilation errors never clear the editor content and never delete the last successful PDF.

## How hallucinations are prevented
- The KB is extracted from explicit resume text only.
- Tailoring uses only evidence claims with `evidence_id` + `source_text`.
- Retrieved evidence is deterministically verified before use.
- Traceability is stored alongside each generated resume (`traceability.json`).

## How fake metrics are prevented
- Metrics are extracted only when explicitly present in the resume text.
- Assembly selects existing evidence claims; it does not invent new numbers.

## How LaTeX formatting is protected
- Bank stores template snapshots (preamble + header) derived from the master resume.
- Assembler uses deterministic wrappers for experience/project item lists.
- Preflight validator prevents unclosed list environments from reaching compilation.

## How keyword stuffing is reduced
- Skills are grouped into recruiter-friendly categories (no “Relevant/Misc/Other” buckets).
- Selection is driven by verified evidence, not uncontrolled keyword injection.

## How random section modifications are avoided
- Top-level section order is fixed and validated.
- Work experience entries are never dropped (only bullet selection changes).

## Where local LLMs are used vs deterministic Python
Used local LLM (Ollama) for:
- JD analysis (structured extraction)

Used deterministic Python for:
- LaTeX parsing
- bank writing + schema validation
- retrieval scoping + evidence verification
- deterministic resume assembly + skills categorization
- LaTeX structure validation + safe compilation
- artifact persistence + preview UI

## Failure handling strategy
The system is conservative:
- If retrieval returns weak/no evidence → fall back to safe per-entry bullets (still evidence-backed).
- If compilation fails → keep last successful PDF preview (if any), keep editor content, show logs.

Default preference:
**Keep original content rather than making unsafe edits.**

## Legacy pipeline (kept as fallback)
The repo still contains the earlier “rewrite planner / safe rewriter / verifier / LaTeX rebuilder” pipeline in `app/pipeline.py` for experimentation/back-compat.
The recommended product flow is bank-first tailoring + deterministic assembly.

## Human review workflow
The supported product UI is **Next.js** (separate frontend repo) and ends in an editable Resume Workspace:
- Edit LaTeX, recompile, preview PDF, export PDF
- View Markdown/Text artifacts and evidence traceability
This keeps final control with the user while preserving evidence constraints.

## Future upgrade path
- Add LangGraph as an orchestration wrapper (without moving business logic into it)
- Improve review UI (diff view, grouping by section, bulk actions)
- Add semantic drift detection via embeddings or LLM judge (with deterministic thresholds)
- Add ATS parser integration and richer match diagnostics
