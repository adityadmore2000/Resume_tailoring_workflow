# Deployment

## What this does
Outlines what you need to deploy the workflow UI + API.

## Why it exists
Deployments should preserve the workflow UX and keep evidence artifacts durable and auditable.

## Step-by-step usage
1. Deploy the Next.js frontend (`resume-tailor-frontend`) as a separate service (e.g. Vercel).
2. Deploy this FastAPI backend as a separate service (e.g. Render/Railway/Fly.io or Docker).
3. Persist `data/` (Experience Banks, vector stores, generated resumes) using durable storage.

## What happens internally
- Experience Banks are written to disk and indexed into a vector store.
- Generated resume artifacts (LaTeX/PDF/traceability/logs) are stored per `resume_id`.

## Common mistakes
- Deploying without persistent storage (you’ll lose banks and generated artifacts).
- Not pinning model configuration (results become non-repeatable).

## Recommended next steps
- Add monitoring for compilation failures and storage usage.
