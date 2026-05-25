# Deployment

## What this does
Outlines what you need to deploy the workflow UI + API.

## Why it exists
Deployments should preserve the workflow UX and keep evidence artifacts durable and auditable.

## Step-by-step usage
1. Run the Streamlit UI as a service (container or VM).
2. Run the FastAPI server (optional, but recommended for integrations).
3. Persist `data/` (Experience Banks, vector stores, generated resumes) using durable storage.

## What happens internally
- Experience Banks are written to disk and indexed into a vector store.
- Generated resume artifacts (LaTeX/PDF/traceability/logs) are stored per `resume_id`.

## Common mistakes
- Deploying without persistent storage (you’ll lose banks and generated artifacts).
- Not pinning model configuration (results become non-repeatable).

## Recommended next steps
- Add monitoring for compilation failures and storage usage.

