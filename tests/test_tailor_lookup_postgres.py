from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.banks_pg.service import BanksService
from app.db.deps import get_db_session
from app.main import create_app


@pytest.mark.asyncio
async def test_tailor_resolves_bank_via_postgres_and_normalizes_slug(db_session, monkeypatch):
    monkeypatch.setenv("QDRANT_URL", ":memory:")

    await BanksService(db_session).create_bank_from_resume_text(
        bank_name="My Bank",
        resume_text="\\section{EXPERIENCE}\\begin{itemize}\\item Did X\\end{itemize}",
        source_format="latex",
        overwrite=False,
    )

    app = create_app()

    async def _override():
        yield db_session

    app.dependency_overrides[get_db_session] = _override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/tailor", json={"bank_name": "My Bank", "jd_text": "python"})
        assert r.status_code == 200
        data = r.json()
        assert data["bank_folder_name"] == "my-bank"
        assert data["status"] == "running"
        assert data["task_id"]


@pytest.mark.asyncio
async def test_tailor_returns_clear_404_when_bank_missing(db_session, monkeypatch):
    monkeypatch.setenv("QDRANT_URL", ":memory:")

    app = create_app()

    async def _override():
        yield db_session

    app.dependency_overrides[get_db_session] = _override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/tailor", json={"bank_name": "does-not-exist", "jd_text": "python"})
        assert r.status_code == 404
        detail = r.json().get("detail")
        assert isinstance(detail, dict)
        assert detail.get("detail") == "Resume not found for selected bank"
        assert detail.get("selected_bank") == "does-not-exist"
        assert detail.get("lookup_mode") in {"slug", "id"}
        assert isinstance(detail.get("available_banks"), list)

