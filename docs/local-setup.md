# Local Setup

## What this does
Shows how to run the platform locally.

## Why it exists
Local runs are useful for fast iteration on your Experience Banks and tailoring workflow.

## Step-by-step usage
1. Create a virtual environment and install dependencies:
   - `python -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -r requirements.txt`
2. Configure environment variables (copy `.env.example`).
   - The backend auto-loads `.env` on startup (OS environment variables still take precedence).
3. Run the backend API:
   - `uvicorn app.main:app --reload --port 8000`
4. Run the frontend UI:
   - In a separate checkout: `cd ../resume-tailor-frontend && npm install && npm run dev`

## What happens internally
- Next.js runs the guided workflow UI (the only supported user-facing UI).
- FastAPI exposes the backend endpoints used by the frontend.

## Common mistakes
- Missing API keys / model config (check `.env.example`).
- Forgetting to install a LaTeX compiler if you want PDF compilation.

## Recommended next steps
- Create your first Experience Bank, then tailor a sample JD to validate end-to-end output.
