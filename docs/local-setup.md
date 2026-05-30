# Local Setup

## What this does
Shows how to run the platform locally.

## Required services
- Postgres (`DATABASE_URL`)
- Qdrant (`QDRANT_URL`)

## Step-by-step usage
1. Create a virtual environment and install dependencies:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
   - `python -m pip install -r requirements.txt`
2. Configure environment variables (via OS env or a local `.env` file):
   - `DATABASE_URL=...`
   - `QDRANT_URL=...`
3. Run DB migrations (one-time) or enable auto-migrate:
   - `alembic upgrade head` (one-time), or set `AUTO_MIGRATE=true`
4. Run the backend API:
   - `uvicorn app.main:app --reload --port 8000`
5. Run the frontend UI:
   - `cd ../resume-tailor-frontend && npm install && npm run dev`

