# Deployment

## Required stateful services
- Postgres (for `resumes` + `resume_nodes`)
- Qdrant (for resume_nodes embeddings)

## Optional persistence
- Persist `data/generated_resumes` if you want generated artifacts (LaTeX/PDF/traceability/logs) to survive restarts.

