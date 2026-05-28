# resume-tailor-backend

FastAPI backend for the Resume Tailor system. Handles experience bank creation, evidence-grounded resume tailoring, LaTeX compilation, and PDF artifact management. Exposes a REST API consumed by the Next.js frontend.

---

## Quick Start (Local)

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your values
```

The backend auto-loads `.env` on startup. OS environment variables take precedence over `.env` values.

### 3. Run database migrations

```bash
alembic upgrade head
# Or set AUTO_MIGRATE=true in .env to run migrations automatically on startup
```

### 4. Start the server

```bash
uvicorn app.main:app --reload --port 8000
```

Backend available at: `http://localhost:8000`
Interactive API docs: `http://localhost:8000/api/docs`

---

## External Dependencies

### Qdrant (required)

Qdrant is the vector store used for semantic retrieval. It must be running before the backend starts — the backend validates connectivity at startup and fails fast with a clear error if Qdrant is unreachable.

```bash
docker run -p 6333:6333 qdrant/qdrant:latest
```

### LLM Provider (required for tailoring)

The backend supports three LLM provider modes configured via `LLM_PROVIDER`:

**Ollama (default, local):**
```bash
ollama pull llama3.2:3b   # default model; works on modest GPUs
ollama serve              # if not already running
```

**OpenAI or OpenAI-compatible:** set the relevant `OPENAI_*` or `OPENAI_COMPATIBLE_*` variables (see Environment Variables below).

### LaTeX Compiler (optional)

Required for `POST /api/resumes/{resume_id}/compile` and PDF endpoints. Without it, `.tex`, `.md`, and `.txt` artifacts are still generated — only compilation and PDF export fail.

Install one of:
- `latexmk` (preferred — handles multi-pass compilation automatically)
- `pdflatex` (fallback)

---

## Environment Variables

| Variable | Description |
|---|---|
| `FRONTEND_URL` | CORS allowlist origin (e.g. `http://localhost:3000`) |
| `VECTOR_STORE_BACKEND` | Default `qdrant` — the only supported runtime backend |
| `QDRANT_URL` | **Required** (e.g. `http://localhost:6333`) |
| `QDRANT_COLLECTION` | Default `resume_tailor_chunks` |
| `LLM_PROVIDER` | `ollama` \| `openai` \| `openai_compatible` |
| `OLLAMA_HOST` | Ollama server URL (when `LLM_PROVIDER=ollama`) |
| `OLLAMA_MODEL` | Model name for generation (default `llama3.2:3b`) |
| `OLLAMA_EMBED_MODEL` | Model name for embeddings |
| `OPENAI_API_KEY` | (when `LLM_PROVIDER=openai`) |
| `OPENAI_BASE_URL` | OpenAI base URL override |
| `OPENAI_MODEL` | Model name for generation |
| `OPENAI_EMBED_MODEL` | Model name for embeddings |
| `OPENAI_COMPATIBLE_BASE_URL` | (when `LLM_PROVIDER=openai_compatible`) |
| `OPENAI_COMPATIBLE_API_KEY` | API key for compatible endpoint |
| `OPENAI_COMPATIBLE_MODEL` | Model name for generation |
| `OPENAI_COMPATIBLE_EMBED_MODEL` | Model name for embeddings |

**Security note:** API keys are read from backend environment variables only and are never forwarded to or exposed by the frontend.

---

## API Overview

### Health
- `GET /api/health`

### Experience Banks
- `GET /api/banks` — list all registered banks
- `POST /api/banks` — create a new bank (upload master resume)
- `GET /api/banks/{bank_name}` — bank metadata
- `GET /api/banks/{bank_name}/tree` — full resume node tree for the bank
- `POST /api/banks/{bank_name}/edit/propose` — propose an edit to a tree node
- `POST /api/banks/{bank_name}/edit/{proposal_id}/apply` — apply a proposed edit
- `POST /api/banks/{bank_name}/edit/{proposal_id}/reject` — reject a proposed edit
- `GET /api/banks/{bank_name}/edit/history` — edit history for the bank

### Tailoring
- `POST /api/tailor` — run a tailoring job against an existing bank

### Tasks
- `GET /api/tasks/{task_id}/progress` — check progress of a long-running background task

### Settings
- `GET /api/settings`
- `PUT /api/settings` (currently returns restart-required)
- `POST /api/settings/test-llm` — verify LLM connectivity
- `POST /api/settings/test-embeddings` — verify embedding model connectivity

### Generated Resumes
- `GET /api/resumes/{resume_id}` — artifact metadata
- `GET /api/resumes/{resume_id}/latex` — current LaTeX source
- `PUT /api/resumes/{resume_id}/latex` — save edited LaTeX
- `POST /api/resumes/{resume_id}/compile` — compile LaTeX to PDF
- `GET /api/resumes/{resume_id}/pdf` — stream the compiled PDF
- `GET /api/resumes/{resume_id}/export/pdf` — download the compiled PDF
- `GET /api/resumes/{resume_id}/markdown` — Markdown version
- `GET /api/resumes/{resume_id}/text` — plain text version
- `GET /api/resumes/{resume_id}/traceability` — bullet → evidence traceability

### Docs
- `GET /api/docs` — docs index
- `GET /api/docs/{slug}` — rendered doc page

---

## Docker (Full Stack)

With `resume-tailor-backend` and `resume-tailor-frontend` checked out as siblings:

```
../resume-tailor-backend
../resume-tailor-frontend
```

```bash
docker compose up --build
```

This starts four services:

| Service | URL |
|---|---|
| Frontend | `http://localhost:3000` |
| Backend | `http://localhost:8000` |
| Qdrant | `http://localhost:6333` |
| Ollama | `http://localhost:11434` |

---

## Architecture Notes

See [`docs/SYSTEM_DESIGN_CLAUDE.md`](docs/SYSTEM_DESIGN_CLAUDE.md) for the full architectural rationale and [`docs/TECHNICAL_DOCUMENTATION_CLAUDE.md`](docs/TECHNICAL_DOCUMENTATION_CLAUDE.md) for module-level details and extension guides.

Key points:

- **Experience banks are the source of truth.** Tailoring never reads the original uploaded resume — it reads only from the bank created during Phase 1.
- **Assembly is deterministic.** The LLM is used only for JD parsing. All resume assembly, evidence verification, and LaTeX construction is done in Python.
- **Qdrant is a retrieval index, not storage.** Structured resume data lives in Postgres; Qdrant holds embeddings and `node_id` payloads for semantic search.
- **Compilation is safe.** A preflight validator checks LaTeX structural integrity before every compile. Errors never clear the editor or delete the last successful PDF.
