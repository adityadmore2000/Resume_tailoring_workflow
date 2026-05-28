# System Design: Evidence-Grounded Resume Tailoring

## The Problem

Tailoring a resume for different job descriptions is tedious by hand. The obvious solution — handing a resume and JD to an LLM and asking it to rewrite — creates its own problems:

- Invented tools and skills the candidate never mentioned
- Made-up impact numbers and percentages
- Broken LaTeX formatting from uncontrolled text edits
- Keyword spam that degrades readability
- Changes to sections the candidate didn't intend to modify

This system takes a different approach: it separates **knowledge representation** from **generation**, and only allows the generation step to work from verified, pre-extracted evidence.

---

## Core Insight: Resume Tailoring Is a Retrieval Problem First

The typical one-prompt resume rewriter conflates three distinct tasks: understanding what the JD needs, deciding what the resume contains, and editing the output. Mixing all three in a single stochastic pass makes it hard to reason about what changed and why.

This system decouples them explicitly:

1. **Build a knowledge base** from the master resume once, with explicit evidence claims.
2. **Retrieve** evidence relevant to the JD from that KB.
3. **Verify** that retrieved evidence is actually supported by what's in the resume.
4. **Assemble** a tailored resume using only verified evidence IDs.

The LLM is only used for structured extraction (JD parsing). All assembly and formatting is deterministic Python.

---

## Two-Phase Product Flow

### Phase 1 — Experience Bank Creation

The user uploads their master resume once. The system processes it into an **experience bank**: a structured, evidence-grounded knowledge base.

Steps:
1. Parse LaTeX into sections and bullets, tracking span positions in the original document.
2. Extract `AtomicEvidenceClaim` records from explicit resume text only — no inference.
3. Derive work and project groupings from LaTeX macros where available.
4. Validate schema constraints (evidence ID integrity, metric linking, required fields).
5. Write markdown and JSON index files from the validated data.
6. Ingest bank chunks into Qdrant (`resume_tailor_chunks` collection), scoped by `bank_folder_name`.
7. Register the bank in `banks_registry.json`.

After this phase, the raw resume is no longer needed. The bank is the source of truth for all subsequent tailoring.

### Phase 2 — Resume Tailoring

The user selects an existing bank and provides a job description. No resume upload is required.

Steps:
1. Parse the JD into structured requirements using an LLM extractor.
2. Retrieve relevant chunks from Qdrant, filtered to the selected bank.
3. Verify each retrieved chunk against JD requirements (`supported / partially_supported / unsupported`).
4. Assemble a tailored resume from verified evidence IDs only.
5. Categorize skills into recruiter-friendly groups, grounded in evidence.
6. Run a LaTeX preflight check and apply safe auto-fixes if needed.
7. Compile the PDF and store all artifacts under a `resume_id`.
8. Open the browser-based LaTeX workspace for review, editing, and export.

---

## Architecture Decisions

### Why separate bank creation from tailoring?

If you tailor directly from the raw resume each time, the LLM sees the entire document on every run. This creates noise, increases hallucination risk, and makes it hard to isolate which parts of the resume were used for which tailoring decision. Creating a bank first forces a clean separation: evidence is extracted once, validated once, and then retrieved selectively.

### Why deterministic assembly instead of LLM-generated output?

Free-form generation can silently change factual content — dates, company names, role titles. The assembler enforces a fixed section order (`HEADER → SUMMARY → EXPERIENCE → PROJECTS → SKILLS → EDUCATION`) and pulls factual metadata from the bank directly. The only things that vary between tailoring runs are which bullets are selected and how skills are grouped.

### Why Qdrant for retrieval, not full-text search?

The JD and resume bullets don't share exact keywords. A JD might say "production ML systems" while the resume says "deployed model inference pipelines." Semantic search handles this mismatch better than keyword matching. Qdrant also supports metadata filtering, which is how bank isolation is enforced — every point is tagged with `bank_folder_name` so retrieval never crosses bank boundaries.

### Why not put everything in Qdrant?

Qdrant is designed for vector search and retrieval, not for structured reads, relational joins, or safe mutations. It doesn't give you transactions, version history, or easy in-place updates. For the experience bank, the source-of-truth storage needs to support editing, versioning, and consistent reads — Qdrant alone can't do that.

The intended storage split is:
- **Postgres + JSONB**: source of truth for structured resume data
- **Qdrant**: semantic retrieval index over that data
- **Local filesystem**: generated artifacts (LaTeX, PDFs, traceability logs)

> **Note on current state:** The system is mid-migration. The FastAPI tailoring path already reads from a Postgres-backed resume tree. Some legacy paths (file-based bank generator, `banks_registry.json`, markdown-first ingestion) are still present in the repo and haven't been fully removed yet.

### Why not a flat table schema for resumes?

A resume is naturally hierarchical: a section contains items, each item has metadata (company, dates, role), and each item has child bullets. Flattening this into separate tables (`experiences`, `projects`, `bullets`) creates a rigid schema that breaks when you add custom sections or want to handle edge cases generically.

The system instead stores the resume as a generic tree:
- `resumes` — one row per bank/resume
- `resume_nodes` — one row per node, with `node_type`, `parent_id`, `position`, and a JSONB `metadata` column

This means factual fields like company name and dates live in `metadata` and are never touched by the LLM. The assembler reads them directly from Postgres and copies them into the output verbatim.

---

## Module Responsibilities

### Resume Parser
Parses LaTeX into structured sections and bullets. Assigns stable bullet IDs. Records `span_start / span_end` positions for each bullet's content in the original document. Extracts a conservative skills list from the Skills section.

**Key constraint:** The LLM never sees or regenerates the full LaTeX as a blob.

### JD Analyzer
Converts raw JD text into a structured `JDAnalysis` JSON: required skills, focus areas, keywords, and rejection risks. This is the only stage that uses an LLM for generation. The analyzer's job is extraction, not judgment about the candidate.

### Bank-Scoped Retrieval
Queries Qdrant for chunks matching the JD embedding, filtered to the selected bank. Returns candidate evidence chunks for the verification step. Cross-bank contamination is prevented by always including `bank_folder_name` as a filter.

### Evidence Verifier
Deterministically classifies whether each retrieved chunk supports a JD requirement. Classification is `supported`, `partially_supported`, or `unsupported`. Missing evidence stays missing — the system doesn't invent it.

### Resume Assembler
Constructs the final resume from verified evidence IDs only. Enforces the fixed section order. Never drops work experience entries; if no verified bullets exist for a company, it falls back to safe per-entry bullets from the bank. Skills are categorized into recruiter-friendly groups (no catch-all "Other" bucket) using evidence-grounded grouping.

### LaTeX Structure Guard
Before compilation, validates structural integrity:
- All `\begin{itemize}` / `\end{itemize}` pairs are balanced
- All custom macro wrappers (`\resumeItemListStart`, `\resumeSubHeadingListStart`, etc.) are balanced
- Exactly one `\begin{document}` and `\end{document}` pair

If an imbalance is detected, it applies safe end-of-document fixes and logs them. Hard errors block compilation; they don't silently corrupt the output.

### Browser LaTeX Workspace
Provides a split-view editor and PDF preview. The user can edit the LaTeX, recompile, export the PDF, and inspect Markdown/text artifacts and the evidence traceability report. Compilation errors never clear the editor or delete the last successful PDF.

---

## Hallucination Prevention

| Risk | Mitigation |
|---|---|
| Invented skills/tools | KB only contains what's explicitly in the resume text |
| Fake metrics | Numbers extracted only when present; assembly never introduces new ones |
| Changed factual metadata | Company names, dates, role titles come from Postgres — not from LLM output |
| Cross-section contamination | Bank isolation enforced at retrieval time by `bank_folder_name` filter |
| Broken LaTeX | Preflight validation + safe auto-fix before every compile |
| Unintended section changes | Fixed section order enforced; work entries are never dropped |

Traceability is stored alongside each generated resume in `traceability.json`, mapping each generated bullet back to its `evidence_id` and `source_text`.

---

## Where the LLM Is Used vs. Deterministic Python

**LLM (Ollama or OpenAI-compatible):**
- JD analysis — structured extraction of requirements, keywords, focus areas

**Deterministic Python:**
- LaTeX parsing
- Bank writing and schema validation
- Retrieval scoping and evidence classification
- Resume assembly and skill categorization
- LaTeX structure validation and compilation
- Artifact persistence and traceability logging

---

## Failure Handling

The system defaults to conservative behavior:
- Weak retrieval → fall back to per-entry bullets from the bank (still evidence-backed, never invented)
- Compilation failure → preserve last successful PDF, keep editor content intact, surface compiler logs
- LLM output that fails schema validation → normalize and retry once; if still invalid, fall back to a safe empty object for non-critical stages, or reject the rewrite and keep the original for critical stages

---

## Legacy Pipeline

The repo still contains an earlier rewrite-based pipeline (`app/pipeline.py`) that used an LLM planner and per-bullet rewriter. It's kept for experimentation and back-compat but is not the recommended path. The bank-first, deterministic-assembly workflow supersedes it.

---

## Planned Evolution

- **LangGraph orchestration**: wrap existing pipeline stages as graph nodes without moving business logic into the graph wiring itself
- **Diff-based review UI**: surface per-section diffs in the workspace instead of full-document view
- **Semantic drift detection**: flag bullets that have drifted significantly from their source evidence using embedding similarity
- **ATS integration**: richer match diagnostics from structured JD parsing

Human review is always the final step. The workspace is designed to keep the user in control of the output, with the evidence constraints acting as guardrails rather than hard locks.
