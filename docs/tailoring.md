# Tailoring

## What this does
Explains how to generate a role-specific resume using a Job Description + a stored bank (Postgres resume tree).

## What happens internally
1. The JD is parsed into structured requirements (LLM extractor).
2. Retrieval runs against Qdrant **resume_nodes**, scoped to the selected `resume_id`.
3. A hierarchy-aware context is built from matched node ids.
4. Eligible bullets are rewritten conservatively using immutable spans stored in Postgres.
5. Artifacts are written under `data/generated_resumes/...` with `traceability.json`.

