from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import AppConfig
from app.api.routers import banks, docs, health, resumes, tailor, tasks, settings, retrieve_debug
from app.db.migrate import upgrade_head
from app.qdrant import QdrantConfig, get_client, healthcheck


def create_app(cfg: AppConfig | None = None) -> FastAPI:
    cfg = cfg or AppConfig.from_env()
    app = FastAPI(title="Resume Tailor Backend", version="1.0")

    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(banks.router)
    app.include_router(tailor.router)
    app.include_router(resumes.router)
    app.include_router(retrieve_debug.router)
    app.include_router(docs.router)
    app.include_router(tasks.router)
    app.include_router(settings.router)

    @app.on_event("startup")
    def _startup_maybe_migrate_db() -> None:
        auto = (os.environ.get("AUTO_MIGRATE") or "").strip().casefold()
        if auto not in {"1", "true", "yes", "on"}:
            return
        upgrade_head()

    @app.on_event("startup")
    def _startup_validate_qdrant() -> None:
        qdrant_url = (cfg.qdrant_url or "").strip()
        if not qdrant_url:
            raise RuntimeError("Qdrant is required. Set QDRANT_URL before starting the backend.")
        try:
            client = get_client(QdrantConfig(url=qdrant_url))
            healthcheck(client=client)
        except Exception as e:
            raise RuntimeError(f"Qdrant is unreachable at QDRANT_URL='{qdrant_url}'. Error: {e}") from e

    return app


app = create_app()
