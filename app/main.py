from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import banks, docs, health, resumes, tailor


def create_app() -> FastAPI:
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
    app.include_router(docs.router)
    return app


app = create_app()

