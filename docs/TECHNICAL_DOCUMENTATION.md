# Technical Documentation: Controlled Local-LLM Resume Tailoring

This document explains how the codebase works, the data contracts, and how to extend the system safely.

## Project structure
```
app/
  main.py                 # CLI entrypoint
  ui.py                   # Streamlit human review UI
  config.py               # Safety + model config
  schemas.py              # Pydantic contracts
  prompts.py              # Back-compat shim for prompts
  parser.py               # LaTeX → structured JSON + spans
  jd_analyzer.py          # JD → JDAnalysis (LLM)
  evidence_mapper.py      # Requirements → evidence in resume (deterministic)
  planner.py              # JSON-only rewrite plan (LLM + heuristic fallback)
  rewriter.py             # Per-bullet rewrite (LLM)
  verifier.py             # Deterministic validation checks
  latex_rebuilder.py      # Surgical LaTeX replacements
  evaluator.py            # Recruiter-style evaluation (LLM)
  pipeline.py             # Orchestrates the stages
  normalizers.py          # Schema-specific output normalization (pre-validation)

  llm/
    local_llm.py           # Ollama client + JSON repair/retry/normalization
    prompts.py             # Schema-explicit prompts per stage

  resume_parser/
    latex_parser.py        # Wrapper for LaTeX parsing (bank generation)
    text_parser.py         # Placeholder for plain-text resumes
    section_detector.py    # Dynamic section detection (heuristic MVP)
    section_mapper.py      # Canonical section mapping

  bank_generator/
    schemas.py             # Experience bank JSON schemas
    folder_manager.py      # bank_folder_name validation + safe paths
    bank_registry.py       # banks_registry.json management
    evidence_extractor.py  # Atomic evidence claim extraction
    capability_mapper.py   # Capability extraction/linking
    validator.py           # Bank validation rules
    markdown_writer.py     # Markdown generation from validated JSON
    bank_builder.py        # End-to-end resume → bank → vector store

  rag/
    chunker.py             # Chunk markdown for retrieval
    ingest.py              # Build per-bank vector store (JSONL)
    retriever.py           # Hybrid retrieval (semantic if available + keywords)

  tailoring/
    jd_parser.py           # Wrapper around JD analysis
    resume_assembler.py    # Loads bank index for tailoring-time constraints
    hallucination_guard.py # Extra guard helpers

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

outputs/
  (generated files)

data/
  uploads/
  experience_bank/
    banks_registry.json
  vector_store/

scripts/
  generate_experience_bank.py
  ingest_experience_bank.py
  list_experience_banks.py
  tailor_resume.py
```

## Data models / schemas
All stage boundaries are defined in `app/schemas.py` using Pydantic.

Key models:
- `ParsedResume`: output of parsing LaTeX.
- `JDAnalysis`: output of JD analyzer.
- `EvidenceMap`: grounded mapping of requirements to resume evidence.
- `RewritePlan`: planner output. JSON-only. No rewriting content here.
- `ChangeReport`: contains `RewriteSuggestion` items with validation flags and status.
- `EvaluationReport`: recruiter-style assessment JSON.

These schemas act as **contracts** between modules, making the pipeline more testable and less prompt-fragile.

## Inputs and outputs
Inputs:
- JD text (string)
- Resume LaTeX (string)

Outputs:
- Tailored LaTeX (string) — produced by applying only user-approved suggestions
- Change report (JSON) — suggestions, reasons, flags
- Evaluation report (JSON) — recruiter-style decision
- Artifacts (JSON) — JD analysis, evidence map, rewrite plan

Experience bank outputs (optional, for bank-driven workflows):
- `data/uploads/<bank>/resume.tex` (source snapshot)
- `data/experience_bank/<bank>/...` (validated markdown + JSON index)
- `data/vector_store/<bank>/index.jsonl` (per-bank retrieval index)
- Registry entry in `data/experience_bank/banks_registry.json`

## CLI usage
Run:
- `python -m app.main --resume examples/sample_resume.tex --jd examples/sample_jd.txt --out outputs/tailored_resume.tex`

### Ollama model prerequisite
The pipeline calls Ollama in multiple stages (JD analysis, planning, rewriting, evaluation). You must have **at least one model installed in Ollama**, and the model name must match what the app is configured to use.

Default:
- `app/config.py` sets `ollama_model = "llama3.2:3b"` (small-model default for modest GPUs)

Check what you have installed:
- `ollama list`

Install the default model:
- `ollama pull llama3.2:3b`

Or use an installed model name instead:
- CLI: pass `--model <installed_model_name>`
- UI: set “Ollama model” in the sidebar

Important CLI behavior:
- Default: **no changes are auto-applied**. The output LaTeX matches the input resume; artifacts are written for review.
- Optional: `--auto-approve-safe` will apply suggestions that pass the verifier. This is intentionally not the default.

Produced files:
- `outputs/tailored_resume.tex`
- `outputs/tailored_resume.change_report.json`
- `outputs/tailored_resume.artifacts.json`
- `outputs/tailored_resume.evaluation.json` (if evaluator enabled)

## UI usage
Run:
- `streamlit run app/ui.py`

UI workflow:
This UI is organized around the two-phase product flow:

1. **Create Experience Bank**
   - Upload a master resume (.tex / .txt)
   - Provide `bank_folder_name` (slugified + validated)
   - Generate KB + vector store + registry entry

2. **Tailor Resume**
   - Select an existing `bank_folder_name`
   - Paste/upload JD
   - Retrieve + verify evidence from the bank
   - Assemble a tailored resume (LaTeX/Markdown/Text)

Important: **Tailoring does not accept a resume input.**

State management:
- `st.session_state` stores the Ollama settings and page-local widget state.

## End-to-end execution flow
There are two primary flows:

### Experience bank generation
Implemented in `app/bank_generator/bank_builder.py`.

### KB-based tailoring
Implemented across:
- `app/tailoring/jd_parser.py`
- `app/rag/retriever.py`
- `app/tailoring/evidence_verifier.py`
- `app/tailoring/resume_assembler.py`

Legacy (fallback) LaTeX editing pipeline is still available in `app/pipeline.py`, but the UI is now bank-first.

## Experience bank generation flow
The bank generator behaves like an evidence-grounded knowledge-base builder (not a resume writer):
1. Validate + slugify `bank_folder_name`
2. Store uploaded resume under `data/uploads/<bank>/resume.tex`
3. Parse LaTeX into bullets/spans (no full regeneration)
4. Extract `AtomicEvidenceClaim` records from explicit resume text
5. Derive work/project groupings from LaTeX macros when available
6. Validate schema constraints (evidence_id integrity, metric linking, etc.)
7. Generate markdown files from validated JSON (deterministic writer)
8. Ingest markdown into per-bank vector store (`index.jsonl`)
9. Update `banks_registry.json`

### Tailored resume output structure (deterministic)
The KB-based assembler enforces a fixed, recruiter/ATS-stable LaTeX layout:
`HEADER (unchanged from bank template) → SUMMARY → EXPERIENCE → PROJECTS → SKILLS → EDUCATION (unchanged snapshot)`

Implementation:
- `app/tailoring/resume_assembler.py`
- `app/tailoring/skill_categorizer.py` (semantic skill grouping + recruiter-friendly category labels)

How “unchanged” works:
- The bank stores a template snapshot derived from the uploaded master resume:
  - `data/experience_bank/<bank>/metadata/template_preamble.tex`
  - `data/experience_bank/<bank>/metadata/template_body_header.tex` (the header block before the first `\\section`)
  - `data/experience_bank/<bank>/metadata/education_section.tex` (education section, without `\\end{document}`)
- Tailoring never reads from `data/uploads/...`; it only uses the stored bank snapshot.

## LLM prompt contracts
Prompts are stored in `app/prompts.py`.

All LLM stages share guardrails:
- resume is source of truth
- do not invent claims
- JSON-only when requested

### JD Analyzer
Input: JD text
Output: `JDAnalysis` JSON

### Planner
Input: (a) `JDAnalysis`, (b) resume bullets (id + plain), (c) evidence map
Output: `RewritePlan` JSON only

### Rewriter (per bullet)
Input: original bullet + keywords + allowed skills/tools
Output: JSON `{ suggested_latex, rationale }`

### Evaluator
Input: tailored resume + JD
Output: `EvaluationReport` JSON

## Why LLM output cannot be trusted directly
Local LLMs frequently return outputs that *look* right to a human but break strict parsers:
- returning a string where a list is expected (`"role_focus": "..."`)
- returning a dict where a string is expected (`"keyword_match_reality": { ... }`)
- returning `"None"` / `"N/A"` as strings instead of `null`/empty lists
- wrapping JSON in markdown fences or adding extra commentary
- minor JSON syntax issues (trailing commas, smart quotes)

In a controlled pipeline, crashing on these cases is unacceptable: the system should recover safely and continue.

## Normalization layer (before Pydantic validation)
All LLM responses are normalized *before* schema validation.

Implementation:
- `app/normalizers.py`
- `app/llm.py` calls `normalize_for_schema(schema.__name__, data)` before `schema.model_validate(...)`

Normalization goals:
- convert strings → `list[str]` when list fields are expected
- convert dicts → readable strings when string fields are expected
- convert `"None"`, `"N/A"`, `""`, `null` → safe defaults
- drop/ignore unexpected shapes instead of guessing

This preserves useful information while preventing schema errors from crashing the app.

## JSON repair + retry strategy
Implemented in `app/llm.py`:
- Extract JSON even if wrapped in markdown code fences.
- Repair common issues:
  - smart quotes → normal quotes
  - trailing commas removed
  - Python-ish dicts (single quotes) parsed via `ast.literal_eval` (safe literal parsing)
- Retry once with stricter “JSON only” instruction if validation fails.
- For *non-critical* stages (JD analysis, planning, evaluation), fall back to a safe empty object if needed.
- For *critical* per-bullet rewrites, malformed outputs cause that rewrite to be rejected (original bullet kept).

## Validation rules
Implemented in `app/verifier.py`.

Deterministic checks (blocking):
- LaTeX safety: balanced braces; no forbidden commands
- Tool hallucination: flag new tool-like tokens not in allowed list (conservative heuristic)
- Fake metrics: new numbers/percentages not present in original bullet
- Keyword stuffing: repeated keywords and excessive density
- Bullet length: too many words

Non-blocking warning:
- semantic drift ratio (`difflib` similarity). Intended as a “red flag”, not an automatic block in MVP.

Verifier behavior:
- If a rewrite fails a blocking check:
  - reject rewrite
  - keep original bullet
  - record rejection reason/flags

## LaTeX rebuild strategy
Implemented in `app/latex_rebuilder.py`.

Key idea:
- The parser records `span_start/span_end` for the bullet **content**, not the `\\item` command.
- The rebuilder applies replacements from the end of the file to the start to avoid offset shifting.
- This preserves margins, spacing, commands, and the overall template.

## Change report structure
`ChangeReport` contains:
- `summary`: counts and quick stats
- `suggestions[]`: list of `RewriteSuggestion` objects:
  - bullet_id
  - original_latex
  - suggested_latex (or null)
  - action (keep|rewrite|remove)
  - reason
  - flags[] (verifier output)
  - status (pending|approved|rejected|risky|unsupported)

## Evaluation report structure
`EvaluationReport` includes:
- ATS match score (0-100)
- Decision (SHORTLISTED/REJECTED)
- Recruiter impression
- Strongest/weakest signals
- Keyword match reality (explicitly calls out superficial matches)
- Human readability verdict
- Remaining unnecessary/weak content

## Error handling
- LLM errors raise `LLMError` from `app/llm.py`.
- Planner stage supports a conservative heuristic fallback (optional).
- Verifier rejects unsafe rewrites instead of attempting to “fix” them with more prompting.

## Testing strategy
Tests are designed to run without Ollama by stubbing the LLM calls.

Focus areas:
- Parser: extracts stable bullet IDs and spans
- Verifier: catches tool hallucinations and fake metrics
- Pipeline: integrates stages and rejects unsafe rewrites deterministically

## How to add a new verifier
1. Implement a new function in `app/verifier.py` returning `VerificationFlag`.
2. Add it to `verify_bullet_rewrite`.
3. Add a unit test in `tests/test_verifier.py` that demonstrates:
   - safe input passes
   - unsafe input fails (blocking) or warns (non-blocking)

## How to add a new LLM provider
Keep the business logic independent of the provider:
1. Create a new client class in `app/llm.py` (e.g., `OpenAIClient`, `LocalHTTPClient`).
2. Ensure it exposes a method compatible with:
   - `chat(system, user) -> str`
   - `generate_json(system, user, schema) -> schema instance`
3. Wire it into CLI/UI by changing construction in `app/main.py` / `app/ui.py`.

## Adding LangGraph later (without rewriting logic)
The pipeline is plain Python functions. To add LangGraph:
- Wrap each stage as a node that calls existing functions:
  - `parse_latex_resume`, `analyze_jd`, `map_evidence`, `plan_rewrites`, `rewrite_bullet`, verifier, rebuild, evaluate
- Do not embed business rules into the graph wiring.
- Keep Pydantic schemas as node I/O contracts.
