# resume-tailor-backend

FastAPI backend for Resume Tailor (AI/RAG/Experience Banks/LaTeX/PDF). This repo exposes a REST API consumed by the Next.js frontend.

## Setup (local)
1. Create a venv and install dependencies:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
   - `python -m pip install -r requirements.txt`
2. Configure environment:
   - `cp .env.example .env` and edit values as needed
3. Run the API:
   - `uvicorn app.main:app --reload --port 8000`

Backend URL: `http://localhost:8000`

## Environment variables
- `FRONTEND_URL` (CORS allowlist origin, e.g. `http://localhost:3000`)
- `QDRANT_URL` (e.g. `http://localhost:6333`)
- `QDRANT_COLLECTION` (default `resume_tailor_chunks`)
- `LLM_PROVIDER` (`ollama` | `openai` | `openai_compatible`)
- `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_EMBED_MODEL` (when `LLM_PROVIDER=ollama`)
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_EMBED_MODEL` (when `LLM_PROVIDER=openai`)
- `OPENAI_COMPATIBLE_BASE_URL`, `OPENAI_COMPATIBLE_API_KEY`, `OPENAI_COMPATIBLE_MODEL`, `OPENAI_COMPATIBLE_EMBED_MODEL` (when `LLM_PROVIDER=openai_compatible`)

Security note: API keys are read from backend environment variables only. Do not expose keys to the frontend.

## API overview
Health:
- `GET /api/health`

Experience Banks:
- `GET /api/banks`
- `POST /api/banks`
- `GET /api/banks/{bank_name}`
- `GET /api/banks/{bank_name}/files`
- `GET /api/banks/{bank_name}/files/content?path=...`

Tailoring:
- `POST /api/tailor`

Generated resumes:
- `GET /api/resumes/{resume_id}`
- `GET /api/resumes/{resume_id}/latex`
- `PUT /api/resumes/{resume_id}/latex`
- `POST /api/resumes/{resume_id}/compile`
- `GET /api/resumes/{resume_id}/pdf`
- `GET /api/resumes/{resume_id}/export/pdf`
- `GET /api/resumes/{resume_id}/markdown`
- `GET /api/resumes/{resume_id}/text`
- `GET /api/resumes/{resume_id}/traceability`

Docs:
- `GET /api/docs`
- `GET /api/docs/{slug}`

## Qdrant setup
Start Qdrant locally:
- `docker run -p 6333:6333 qdrant/qdrant:latest`

If `QDRANT_URL` is set, the backend will attempt to upsert embeddings during bank ingestion and use Qdrant for semantic retrieval (falling back to the local JSONL store if Qdrant is unavailable).

## LaTeX compiler setup
For `POST /api/resumes/{resume_id}/compile` and PDF endpoints you need one of:
- `latexmk` (preferred)
- `pdflatex` (fallback)

Without a LaTeX compiler, the backend still generates `.tex`/`.md`/`.txt` artifacts, but compilation/PDF endpoints will fail.

## Docker (backend + frontend + Qdrant + Ollama)
If you have the frontend repo checked out next to this repo:
```
../resume-tailor-backend
../resume-tailor-frontend
```

Run everything:
- `docker compose up --build`

Services:
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Qdrant: `http://localhost:6333`
- Ollama: `http://localhost:11434`

