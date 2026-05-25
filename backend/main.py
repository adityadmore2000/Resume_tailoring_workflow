from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import banks, docs, health, resumes, tailor


def create_app() -> FastAPI:
    app = FastAPI(title="Resume Tailoring Backend", version="1.0")

    # Local dev: Next.js on :3000
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(banks.router)
    app.include_router(tailor.router)
    app.include_router(resumes.router)
    app.include_router(docs.router)
    return app


app = create_app()

