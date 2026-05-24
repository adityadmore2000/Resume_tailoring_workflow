# Technical Documentation: Controlled Local-LLM Resume Tailoring

This document explains how the codebase works, the data contracts, and how to extend the system safely.

## Project structure
```
app/
  main.py                 # CLI entrypoint
  ui.py                   # Streamlit human review UI
  config.py               # Safety + model config
  schemas.py              # Pydantic contracts
  prompts.py              # Prompt templates (per stage)
  llm.py                  # Ollama client + JSON extraction
  parser.py               # LaTeX → structured JSON + spans
  jd_analyzer.py          # JD → JDAnalysis (LLM)
  evidence_mapper.py      # Requirements → evidence in resume (deterministic)
  planner.py              # JSON-only rewrite plan (LLM + heuristic fallback)
  rewriter.py             # Per-bullet rewrite (LLM)
  verifier.py             # Deterministic validation checks
  latex_rebuilder.py      # Surgical LaTeX replacements
  evaluator.py            # Recruiter-style evaluation (LLM)
  pipeline.py             # Orchestrates the stages

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
1. Paste/upload JD and resume
2. Run pipeline
3. Inspect artifacts (JD analysis + evidence map)
4. Review each suggestion:
   - original vs suggested
   - reason
   - validation flags
   - verifier rejection status
5. Approve individual changes
6. Generate final LaTeX only from approvals
7. Download tailored `.tex` and JSON reports

State management:
- `st.session_state` stores `pipeline_result`, `parsed_resume`, and the generated `final_tex`.
- Approvals are tracked per bullet ID using checkbox keys.

## End-to-end execution flow
The primary orchestrator is `app/pipeline.py:run_pipeline`:
1. Parse resume (`parse_latex_resume`)
2. Analyze JD (`analyze_jd` via Ollama)
3. Map evidence (`map_evidence`)
4. Plan changes (`plan_rewrites` via Ollama; optional fallback to `heuristic_plan`)
5. Rewrite bullets (`rewrite_bullet` per bullet)
6. Verify rewrites (`verify_bullet_rewrite`)
7. Produce `ChangeReport` (suggestions + flags)
8. Evaluate (optional) (`evaluate_tailored_resume`)

Applying changes:
- The pipeline returns suggestions as *pending*.
- The UI or CLI marks suggestions as `approved`.
- The rebuilder applies replacements (`rebuild_latex`).

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
