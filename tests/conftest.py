from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

# Ensure repository root is importable (so `import app` works without installation).
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _test_database_url() -> str | None:
    url = (os.environ.get("TEST_DATABASE_URL") or "").strip()
    return url or None


@pytest.fixture(scope="session")
def db_url() -> str:
    url = _test_database_url()
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run Postgres-backed DB tests.")
    return url


@pytest.fixture(scope="session")
def _run_alembic_migrations(db_url: str) -> None:
    os.environ["DATABASE_URL"] = db_url
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")


@pytest.fixture()
async def db_session(db_url: str, _run_alembic_migrations: None, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", db_url)
    from app.db.session import get_sessionmaker

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(text("TRUNCATE resume_nodes, resumes RESTART IDENTITY CASCADE"))
        await session.commit()
        yield session
