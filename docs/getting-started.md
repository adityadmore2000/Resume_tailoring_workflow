# Getting Started

## What this does
Helps you move from a single “master resume” to repeatable tailoring for multiple job descriptions.

## Runtime architecture (source of truth)
- Postgres `resumes` + `resume_nodes` store your bank and resume tree.
- Qdrant `resume_nodes` index provides semantic retrieval scoped by `resume_id`.
- Generated artifacts are written to `data/generated_resumes/...`.

## Step-by-step usage
1. **Create a bank** (upload/paste your master resume). This writes `resumes` + `resume_nodes` to Postgres.
2. **Preview** the bank’s items/tree (optional sanity-check).
3. **Tailor a resume** (paste a Job Description; select the bank).
4. **Review & export** in the Resume Workspace (edit LaTeX, recompile, export PDF).

