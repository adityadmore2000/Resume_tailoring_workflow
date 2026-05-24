# System Design: Controlled Local-LLM Resume Tailoring

## What problem this solves
Tailoring a resume for different job descriptions often requires repeated manual edits: rephrasing bullets, emphasizing the most relevant experience, and removing low-signal content. The risky part is that typical “AI resume rewriters” can:
- hallucinate tools/skills you don’t have
- invent metrics and impact
- break LaTeX formatting
- spam keywords and hurt readability
- rewrite random sections you did not intend to change

This system is built to solve that problem **safely** by treating the LLM as a **controlled editor** inside a deterministic pipeline.

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
- **extraction** (JD analyzer)
- **grounding** (evidence mapper)
- **planning** (rewrite planner → JSON only)
- **editing** (safe rewrite engine per-bullet)
- **verification** (deterministic checks)
- **application** (surgical LaTeX rebuilding)
- **evaluation** (separate LLM evaluator)

## Core design principle
- **Resume is the source of truth:** if it is not in the resume, the system does not add it.
- **JD is only a relevance signal:** it influences *priorities and phrasing*, not factual claims.
- **LLM is a controlled editor:** it rewrites text, but does not create new evidence.
- **Validation + human approval:** unsafe changes are rejected; safe changes are still user-approved.

## High-level architecture
Modules live in `app/` and are orchestrated by `app/pipeline.py`.

Pipeline stages:
1. **Resume Parser** (`app/parser.py`)
2. **JD Analyzer** (`app/jd_analyzer.py`) via Ollama
3. **Evidence Mapper** (`app/evidence_mapper.py`) deterministic
4. **Rewrite Planner** (`app/planner.py`) via Ollama (JSON-only)
5. **Safe Rewrite Engine** (`app/rewriter.py`) per bullet via Ollama
6. **Rule-Based Verifier** (`app/verifier.py`) deterministic checks
7. **LaTeX Rebuilder** (`app/latex_rebuilder.py`) surgical replacement
8. **Final Evaluator** (`app/evaluator.py`) via Ollama (separate role)

## Pipeline flow (conceptual)
Input:
- JD text
- Master resume LaTeX

Intermediate artifacts:
- `ParsedResume` (structured bullets + spans)
- `JDAnalysis` (structured requirements)
- `EvidenceMap` (matches grounded in resume)
- `RewritePlan` (what to rewrite/remove/keep)
- `ChangeReport` (suggestions + validation flags)

Output:
- Tailored LaTeX resume (only after approvals)
- Change report
- Recruiter-style evaluation report

## Module responsibilities
### 1) Resume Parser
Responsibility:
- Parse LaTeX into a structured form (sections + bullets).
- Assign stable bullet IDs.
- Track *span positions* for each bullet content in the original LaTeX.
- Extract a conservative list of skills/tools from the Skills section.

Key safety choice:
- The LLM never sees or edits the full LaTeX document as a single blob to “regenerate”.

### 2) JD Analyzer (LLM)
Responsibility:
- Convert JD text into structured JSON: skills, focus areas, keywords, rejection risks.

Key safety choice:
- The analyzer is an extractor. It does not claim anything about the candidate.

### 3) Evidence Mapper (deterministic)
Responsibility:
- Map JD requirements only to evidence that already exists in the resume.
- Mark each requirement as `strong_match`, `partial_match`, or `missing`.

Key safety choice:
- Missing evidence is reported as missing; it is not added.

### 4) Rewrite Planner (LLM, JSON-only)
Responsibility:
- Decide which bullets should be kept/rewritten/removed and why.
- Output JSON only. No rewriting here.

Key safety choice:
- Separating planning from rewriting prevents the model from “helpfully” inventing content while deciding priorities.

### 5) Safe Rewrite Engine (LLM, per bullet)
Responsibility:
- Rewrite only a single bullet at a time based on the plan.
- Respect constraints (no new tools/metrics/deployments).

Key safety choice:
- Small input scope reduces accidental template damage and makes validation easier.

### 6) Rule-Based Verifier (deterministic)
Responsibility:
- Block risky edits:
  - tool hallucinations
  - fake metrics
  - LaTeX safety issues
  - keyword stuffing
  - overlong bullets
- Optionally warn on semantic drift (non-blocking warning by default).

Key safety choice:
- The verifier is deterministic Python, not an LLM.

### 7) LaTeX Rebuilder
Responsibility:
- Apply approved edits by replacing only known text spans.
- Preserve formatting, structure, and template.

Key safety choice:
- Never regenerate the entire LaTeX file; only replace the bullet content spans.

### 8) Final Evaluator (LLM)
Responsibility:
- Provide a recruiter-style evaluation (ATS score, decision, strengths/weaknesses).

Key safety choice:
- Evaluator is separate from the editor to reduce self-justifying bias.

## How hallucinations are prevented
- Evidence mapping never invents evidence.
- Rewrite engine is constrained by allowed tools/skills extracted from the resume.
- Verifier rejects tool-like additions not supported by the extracted lists.
- Human review UI shows every change side-by-side.

## How fake metrics are prevented
- Verifier blocks newly introduced numbers/percentages not present in the original bullet.
- Rewrite prompt explicitly bans new metrics.

## How LaTeX formatting is protected
- LLM edits are limited to bullet content spans (not document structure).
- Verifier checks for unbalanced braces and forbidden commands.
- Rebuilder applies surgical replacements only.

## How keyword stuffing is reduced
- Verifier detects high keyword density and excessive repetition.
- Prompts prefer clarity over buzzwords.

## How random section modifications are avoided
- Only bullets in the plan are eligible for rewriting.
- Rebuilder replaces only the spans that correspond to those bullets.

## Where local LLMs are used vs deterministic Python
Used local LLM (Ollama) for:
- JD analysis (structured extraction)
- rewrite planning (JSON-only decisions)
- bullet rewriting (editor role)
- final evaluation (recruiter role)

Used deterministic Python for:
- LaTeX parsing
- evidence mapping
- validation and safety checks
- LaTeX rebuilding
- UI approval gating

## Failure handling strategy
The system is conservative:
- If any rewrite fails validation → reject rewrite → keep original bullet → record reason.
- If planner fails → fallback heuristic planner (optional).
- If evaluator fails → keep tailoring artifacts and UI still works.

Default preference:
**Keep original content rather than making unsafe edits.**

## Human-in-the-loop review workflow
The Streamlit UI is the control panel:
- Show original and suggested text side-by-side
- Show reasons + validation flags
- Block rejected suggestions
- Require explicit approval for each change
- Only apply approved changes

## Future upgrade path
- Add LangGraph as an orchestration wrapper (without moving business logic into it)
- Improve review UI (diff view, grouping by section, bulk actions)
- Add semantic drift detection via embeddings or LLM judge (with deterministic thresholds)
- Add PDF export (`pdflatex` or `tectonic`)
- Add ATS parser integration and richer match diagnostics

