from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config


def upgrade_head(*, alembic_ini_path: str | None = None) -> None:
    """
    Run `alembic upgrade head` using the repo's `alembic.ini`.

    Requires `DATABASE_URL` to be set (async URL is fine: postgresql+asyncpg://...).
    """

    ini = alembic_ini_path
    if not ini:
        repo_root = Path(__file__).resolve().parents[2]
        ini = str(repo_root / "alembic.ini")

    if not (os.environ.get("DATABASE_URL") or "").strip():
        raise RuntimeError("DATABASE_URL is not set; cannot run migrations.")

    cfg = Config(ini)
    command.upgrade(cfg, "head")

