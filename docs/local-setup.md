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
3. Run the UI:
   - `streamlit run app/ui.py`
4. (Optional) Run the API server:
   - `uvicorn app.ui.api.server:app --reload`

## What happens internally
- Streamlit runs the guided workflow UI.
- FastAPI exposes programmatic endpoints for bank preview and resume workspace artifacts.

## Common mistakes
- Missing API keys / model config (check `.env.example`).
- Forgetting to install a LaTeX compiler if you want PDF compilation.

## Recommended next steps
- Create your first Experience Bank, then tailor a sample JD to validate end-to-end output.

