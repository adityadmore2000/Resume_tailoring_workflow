# Technical Documentation

## Supported runtime architecture (only)
The backend supports exactly one runtime architecture:
- Postgres source of truth:
  - `resumes`
  - `resume_nodes`
- Qdrant index:
  - resume_nodes semantic retrieval collection (points keyed by `node_id`, filtered by `resume_id`)
- Generated artifacts on disk:
  - `data/generated_resumes/<bank_slug>/<resume_id>/...`

There is no supported runtime path that reads local file-based experience banks (no `data/experience_bank/`, no `banks_registry.json`, no `experience_bank_index.json`).

## Repository layout (relevant modules)
```
app/
  main.py                 # FastAPI entrypoint (uvicorn app.main:app)
  config.py               # Central config (env-driven)
  qdrant.py               # Qdrant client helpers

  api/                    # FastAPI routers
  banks_pg/               # Postgres-backed bank/resume CRUD
  db/                     # SQLAlchemy models + sessions + migrations
  generated_resumes/      # Generated resume artifact store + LaTeX compile helpers
  llm/                    # LLM provider abstraction + factories
  resume_tree/            # resume_nodes tree services + Qdrant resume_nodes index
  tailoring/              # JD parsing + hierarchy context building

docs/
  SYSTEM_DESIGN.md
  TECHNICAL_DOCUMENTATION.md
```

## Environment variables
Required:
- `DATABASE_URL` (Postgres)
- `QDRANT_URL` (Qdrant)

Optional:
- `QDRANT_COLLECTION` (base name; resume_nodes collection is derived as `<base>_resume_nodes`)
- `QDRANT_RESUME_NODES_COLLECTION` (explicit override for the resume_nodes collection name)
- `FRONTEND_URL` (CORS allowlist origin, default `http://localhost:3000`)
- `AUTO_MIGRATE` (`true`/`false`) to auto-run Alembic migrations at startup

LLM provider selection:
- `LLM_PROVIDER` (`ollama` | `openai` | `openai_compatible`)
- Ollama: `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_EMBED_MODEL`
- OpenAI: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_EMBED_MODEL`
- OpenAI-compatible: `OPENAI_COMPATIBLE_BASE_URL`, `OPENAI_COMPATIBLE_API_KEY`, `OPENAI_COMPATIBLE_MODEL`, `OPENAI_COMPATIBLE_EMBED_MODEL`

## Postgres schema notes
- `resumes`:
  - `slug`: stable bank identifier used by the UI (e.g. `my-bank`)
  - `metadata.source_resume_tex`: the original LaTeX source used for span-based rewriting
- `resume_nodes`:
  - hierarchical tree: root → sections → items → details
  - `metadata.searchable=true` opts a node into semantic indexing
  - `metadata.immutable_fields.span_start/span_end` are used for safe LaTeX replacement

## Qdrant resume_nodes index
- One point per indexed node (`id = node_id`)
- Payload includes `resume_id` (mandatory filter for scoping) plus helpful metadata (section label, tools/skills)
- The index can be rebuilt idempotently from Postgres at any time

## Generated resumes layout
Artifacts are written under:
`data/generated_resumes/<bank_slug>/<resume_id>/`

Files include:
- `resume.tex`
- `resume.pdf` (optional; only if a LaTeX compiler is available)
- `compile.log`
- `traceability.json`
- `metadata.json`

## API reference
See `resume-tailor-backend/README.md` and the router implementations under `app/api/routers/`.

