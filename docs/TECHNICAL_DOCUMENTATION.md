# Technical Documentation: Resume Tailoring Backend

This document covers how the codebase is structured, what each module is responsible for, the data contracts between stages, and how to extend the system without breaking its safety guarantees.

---

## Project Structure

```
app/
  main.py                 # FastAPI entrypoint (uvicorn app.main:app)
  legacy_cli.py           # Legacy CLI pipeline entrypoint
  config.py               # Model config and safety settings
  schemas.py              # Pydantic data contracts (all stage boundaries)
  prompts.py              # Back-compat shim for legacy prompts
  normalizers.py          # LLM output normalization (runs before Pydantic validation)

  parser.py               # LaTeX → structured JSON + span positions
  jd_analyzer.py          # JD text → JDAnalysis JSON (LLM)
  evidence_mapper.py      # JD requirements → resume evidence mapping (deterministic)
  planner.py              # JSON-only rewrite plan (LLM + heuristic fallback)
  rewriter.py             # Per-bullet rewrite (LLM)
  verifier.py             # Deterministic validation checks on rewrites
  latex_rebuilder.py      # Surgical span-based LaTeX replacements
  evaluator.py            # Recruiter-style evaluation (LLM)
  pipeline.py             # Legacy pipeline orchestration (kept for back-compat)

  llm/
    local_llm.py          # Provider abstraction (Ollama/OpenAI/OpenAI-compatible)
                          # Includes JSON repair, retry logic, and normalization
    prompts.py            # Schema-explicit prompts for each pipeline stage

  resume_parser/
    latex_parser.py       # LaTeX parsing wrapper (used during bank generation)
    text_parser.py        # Plain-text resume parser (placeholder, not fully implemented)
    section_detector.py   # Heuristic section boundary detection
    section_mapper.py     # Maps detected sections to canonical section names

  bank_generator/
    schemas.py            # Experience bank JSON schemas
    folder_manager.py     # bank_folder_name validation and safe path construction
    bank_registry.py      # banks_registry.json read/write
    evidence_extractor.py # Atomic evidence claim extraction from parsed resume
    capability_mapper.py  # Capability extraction and evidence linking
    validator.py          # Bank validation rules (schema constraints, ID integrity)
    markdown_writer.py    # Generates markdown files from validated bank JSON
    bank_builder.py       # End-to-end: resume → bank → vector store

  rag/
    chunker.py            # Splits bank markdown into retrieval chunks
    ingest.py             # Qdrant ingestion (Qdrant-only runtime)
    retriever.py          # Qdrant retrieval, scoped by bank_folder_name

  tailoring/
    jd_parser.py          # Wrapper around JD analysis
    resume_assembler.py   # Deterministic LaTeX assembly from verified bank evidence
    hallucination_guard.py # Additional guard helpers for assembly
    skill_categorizer.py  # Evidence-grounded skill grouping with category labels

  generated_resumes/
    resume_store.py       # Writes per-resume artifacts to data/generated_resumes/...
    latex_structure.py    # LaTeX list/macro structure validation + safe auto-fix
    latex_compiler.py     # latexmk/pdflatex wrapper with timeouts and preflight

docs/
  SYSTEM_DESIGN.md
  TECHNICAL_DOCUMENTATION.md

tests/
  test_parser.py
  test_verifier.py
  test_pipeline.py

examples/
  sample_resume.tex
  sample_jd.txt

data/
  uploads/
  experience_bank/
    banks_registry.json
  vector_store/
  generated_resumes/

scripts/
  generate_experience_bank.py
  ingest_experience_bank.py
  list_experience_banks.py
  tailor_resume.py
```

---

## Data Models and Stage Contracts

All stage boundaries are defined in `app/schemas.py` using Pydantic. These schemas serve as explicit contracts between modules, which makes individual stages testable in isolation and keeps the pipeline from being brittle to prompt changes.

Key models:

| Model | Description |
|---|---|
| `ParsedResume` | Output of LaTeX parsing: sections, bullets, span positions |
| `JDAnalysis` | Structured JD output: skills, focus areas, keywords, rejection risks |
| `EvidenceMap` | Grounded mapping of JD requirements to resume evidence |
| `RewritePlan` | Planner output — JSON only, no rewrite content |
| `ChangeReport` | Contains `RewriteSuggestion` items with flags, status, and rationale |
| `EvaluationReport` | Recruiter-style assessment including ATS match score and keyword reality check |

---

## Inputs and Outputs

**Phase 1 — Bank creation:**
- Input: master resume (`.tex` or plain text)
- Outputs:
  - `data/uploads/<bank>/resume.tex` — source snapshot
  - `data/experience_bank/<bank>/` — validated markdown and JSON index
  - Qdrant collection `resume_tailor_chunks` — bank-scoped embedding points
  - `data/experience_bank/banks_registry.json` — registry entry

**Phase 2 — Tailoring:**
- Inputs: `bank_folder_name` (selected bank) + JD text
- Outputs per `resume_id` under `data/generated_resumes/<bank>/<resume_id>/`:
  - `resume.tex` — tailored LaTeX
  - `resume.pdf` — compiled PDF (if compilation succeeds)
  - `tailored_resume.md` — Markdown version
  - `tailored_resume.txt` — plain text version
  - `traceability.json` — bullet → evidence_id → source_text mapping
  - `compile.log` — compiler output and preflight notes
  - `metadata.json` — paths and compile status

---

## Local Development Setup

### Prerequisites

- Python 3.10+
- One of: Ollama, OpenAI API access, or an OpenAI-compatible endpoint
- Qdrant running locally (`docker run -p 6333:6333 qdrant/qdrant:latest`)
- `latexmk` or `pdflatex` for PDF compilation (optional — non-PDF artifacts still work without it)

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env as needed

# For Postgres: run migrations, or set AUTO_MIGRATE=true
alembic upgrade head

uvicorn app.main:app --reload --port 8000
```

### Ollama Model

The pipeline uses Ollama by default. You need at least one model installed:

```bash
ollama list              # check what's installed
ollama pull llama3.2:3b  # install the default (small, works on modest GPUs)
```

The model name is configured in `app/config.py` (`ollama_model = "llama3.2:3b"`). You can override it via the `OLLAMA_MODEL` environment variable or through the Settings UI.

### Environment Variables

| Variable | Description |
|---|---|
| `FRONTEND_URL` | CORS allowlist origin (e.g. `http://localhost:3000`) |
| `VECTOR_STORE_BACKEND` | Default `qdrant` — only supported runtime |
| `QDRANT_URL` | Required (e.g. `http://localhost:6333`) |
| `QDRANT_COLLECTION` | Default `resume_tailor_chunks` |
| `LLM_PROVIDER` | `ollama` \| `openai` \| `openai_compatible` |
| `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_EMBED_MODEL` | When `LLM_PROVIDER=ollama` |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_EMBED_MODEL` | When `LLM_PROVIDER=openai` |
| `OPENAI_COMPATIBLE_BASE_URL`, `OPENAI_COMPATIBLE_API_KEY`, `OPENAI_COMPATIBLE_MODEL`, `OPENAI_COMPATIBLE_EMBED_MODEL` | When `LLM_PROVIDER=openai_compatible` |

API keys are read from backend environment variables only and are never exposed to the frontend.

---

## Experience Bank Generation Flow

Implemented in `app/bank_generator/bank_builder.py`.

1. Validate and slugify `bank_folder_name`
2. Store uploaded resume under `data/uploads/<bank>/resume.tex`
3. Parse LaTeX into bullets and spans (no full document regeneration)
4. Extract `AtomicEvidenceClaim` records from explicit resume text
5. Derive work and project groupings from LaTeX macros where available
6. Validate schema constraints (evidence ID integrity, metric linking, required fields)
7. Write markdown and JSON index files deterministically from validated data
8. Ingest markdown chunks into Qdrant (`resume_tailor_chunks`)
9. Update `banks_registry.json`

---

## Tailored Resume Assembly

Implemented in `app/tailoring/resume_assembler.py` and `app/tailoring/skill_categorizer.py`.

The assembler enforces a fixed, ATS-stable section order:

```
HEADER (unchanged from bank template)
→ SUMMARY
→ EXPERIENCE
→ PROJECTS
→ SKILLS
→ EDUCATION (unchanged snapshot)
```

The `HEADER` and `EDUCATION` blocks are copied verbatim from bank template snapshots:
- `data/experience_bank/<bank>/metadata/template_preamble.tex`
- `data/experience_bank/<bank>/metadata/template_body_header.tex`
- `data/experience_bank/<bank>/metadata/education_section.tex`

The assembler never reads from `data/uploads/`. It only uses the stored bank snapshot. This makes tailoring fully independent of the original upload after bank creation.

---

## Generated Resume Workspace

After tailoring, the system writes all artifacts under `data/generated_resumes/<bank>/<resume_id>/` and opens a browser-based LaTeX workspace.

The Next.js frontend loads artifacts via REST:

| Endpoint | Description |
|---|---|
| `GET /api/resumes/{resume_id}` | Resume metadata and paths |
| `GET /api/resumes/{resume_id}/latex` | Current LaTeX source |
| `PUT /api/resumes/{resume_id}/latex` | Save edited LaTeX |
| `POST /api/resumes/{resume_id}/compile` | Compile to PDF |
| `GET /api/resumes/{resume_id}/pdf` | Stream the PDF |
| `GET /api/resumes/{resume_id}/export/pdf` | Download the PDF |
| `GET /api/resumes/{resume_id}/markdown` | Markdown version |
| `GET /api/resumes/{resume_id}/text` | Plain text version |
| `GET /api/resumes/{resume_id}/traceability` | Evidence traceability |

### LaTeX Preflight Validation

Before every compilation, `app/generated_resumes/latex_structure.py` validates structural integrity:

- Every `\begin{itemize}` has a matching `\end{itemize}`
- `\resumeItemListStart` matches `\resumeItemListEnd`
- `\resumeSubHeadingListStart` matches `\resumeSubHeadingListEnd`
- Exactly one `\begin{document}` and one `\end{document}`

If unclosed list environments are found, the system inserts the missing closers before `\end{document}` and logs the auto-fix. This prevents common assembler edge cases from reaching the compiler.

---

## LLM Output Reliability

Local LLMs frequently produce output that looks correct to a human but fails strict parsers. Common failure modes:

- Returning a string where a list is expected (e.g., `"role_focus": "backend"` instead of `["backend"]`)
- Returning a dict where a string is expected
- Using `"None"` or `"N/A"` as strings instead of `null` or empty lists
- Wrapping JSON in markdown fences with extra commentary
- Minor JSON syntax issues: trailing commas, smart quotes, single-quoted dicts

### Normalization Layer

All LLM responses pass through `app/normalizers.py` before Pydantic validation. The normalizer:

- Converts strings to `list[str]` where list fields are expected
- Converts unexpected dicts to readable strings where string fields are expected
- Converts `"None"`, `"N/A"`, `""`, and `null` to safe defaults
- Drops unexpected shapes rather than guessing

This preserves useful partial output while preventing validation errors from crashing the pipeline.

### JSON Repair and Retry

Implemented in `app/llm/local_llm.py`:

1. Extract JSON even if wrapped in markdown fences
2. Repair common issues: smart quotes → standard quotes, trailing commas removed, Python-style single-quoted dicts parsed via `ast.literal_eval`
3. Retry once with a stricter "JSON only" instruction if validation still fails
4. For non-critical stages (JD analysis, planning, evaluation): fall back to a safe empty object if repair fails
5. For critical per-bullet rewrites: malformed output causes the rewrite to be rejected and the original bullet kept

---

## Validation and Verification

Implemented in `app/verifier.py`. All checks are deterministic — no LLM involved.

**Blocking checks (rewrite rejected if any fail):**
- **LaTeX safety**: balanced braces, no forbidden commands
- **Tool hallucination**: new tool-like tokens not present in the allowed list
- **Fake metrics**: new numbers or percentages not found in the original bullet
- **Keyword stuffing**: excessive keyword density or repetition
- **Bullet length**: exceeds maximum word count

**Non-blocking warning:**
- **Semantic drift**: `difflib` similarity ratio below threshold — logged as a red flag but doesn't auto-reject in the current implementation

When a rewrite fails a blocking check, the original bullet is kept and the rejection reason is recorded in the `ChangeReport`.

---

## LaTeX Span Rebuild Strategy

Implemented in `app/latex_rebuilder.py`.

The parser records `span_start / span_end` for each bullet's **content**, not the surrounding `\item` command. The rebuilder applies replacements from the end of the document to the start, which avoids the offset-shifting problem that occurs when earlier replacements change character positions.

This approach preserves margins, spacing, custom commands, and the overall template structure, while making surgical content changes.

---

## LLM Prompt Contracts

Each LLM stage has an explicit prompt in `app/llm/prompts.py` with the output schema embedded. All prompts share a consistent set of guardrails:

- The resume is the source of truth
- Do not invent claims, metrics, or tools
- Output JSON only (when applicable)

Stage-level contracts:

| Stage | Input | Output |
|---|---|---|
| JD Analyzer | JD text | `JDAnalysis` JSON |
| Planner | `JDAnalysis` + bullet list + evidence map | `RewritePlan` JSON |
| Rewriter | Original bullet + allowed skills/keywords | `{ suggested_latex, rationale }` JSON |
| Evaluator | Tailored resume + JD | `EvaluationReport` JSON |

---

## API Reference

Full interactive docs are available at `http://localhost:8000/api/docs` when the server is running.

**Health:** `GET /api/health`

**Experience Banks:**
- `GET /api/banks` — list all banks
- `POST /api/banks` — create a new bank (upload resume)
- `GET /api/banks/{bank_name}` — bank metadata
- `GET /api/banks/{bank_name}/tree` — full resume tree for the bank
- `POST /api/banks/{bank_name}/edit/propose` — propose a tree node edit
- `POST /api/banks/{bank_name}/edit/{proposal_id}/apply` — apply proposed edit
- `POST /api/banks/{bank_name}/edit/{proposal_id}/reject` — reject proposed edit
- `GET /api/banks/{bank_name}/edit/history` — edit history

**Tailoring:** `POST /api/tailor`

**Tasks:** `GET /api/tasks/{task_id}/progress` — poll long-running task progress

**Settings:**
- `GET /api/settings`
- `PUT /api/settings` (returns restart-required)
- `POST /api/settings/test-llm`
- `POST /api/settings/test-embeddings`

**Generated Resumes:** See table in the "Generated Resume Workspace" section above.

**Docs:** `GET /api/docs`, `GET /api/docs/{slug}`

---

## Testing

Tests are designed to run without Ollama by stubbing LLM calls.

```bash
pytest tests/
```

Coverage focus:
- **Parser**: stable bullet ID extraction and span accuracy
- **Verifier**: blocks tool hallucinations and fake metrics deterministically
- **Pipeline**: integration of stages, correct rejection of unsafe rewrites

### Adding a New Verifier Check

1. Implement a new function in `app/verifier.py` returning `VerificationFlag`
2. Add it to `verify_bullet_rewrite`
3. Add a unit test in `tests/test_verifier.py` covering both a safe pass case and an unsafe fail case

### Adding a New LLM Provider

Business logic is provider-agnostic:

1. Create a new client class in `app/llm/local_llm.py`
2. Expose a compatible interface: `chat(system, user) -> str` and `generate_json(system, user, schema) -> schema instance`
3. Wire it through `app/llm/factory.py`

### Adding LangGraph Later

The pipeline is plain Python functions, which makes wrapping them in a graph straightforward when needed:

- Wrap each stage as a node calling the existing function (e.g., `parse_latex_resume`, `analyze_jd`, `map_evidence`, `plan_rewrites`, `rewrite_bullet`, etc.)
- Keep business rules inside the functions, not in the graph wiring
- Use the existing Pydantic schemas as node I/O contracts

---

## Docker (Full Stack)

With `resume-tailor-backend` and `resume-tailor-frontend` checked out as siblings:

```
../resume-tailor-backend
../resume-tailor-frontend
```

```bash
docker compose up --build
```

Services:
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Qdrant: `http://localhost:6333`
- Ollama: `http://localhost:11434`
