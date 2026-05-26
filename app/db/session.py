from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def _load_dotenv_early() -> None:
    try:
        cwd_env = os.path.join(os.getcwd(), ".env")
        if os.path.exists(cwd_env):
            load_dotenv(dotenv_path=cwd_env, override=False)
        else:
            load_dotenv(override=False)
    except Exception:
        return


_load_dotenv_early()


def _database_url() -> str:
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set.")
    return url


@lru_cache(maxsize=1)
def get_async_engine() -> AsyncEngine:
    return create_async_engine(_database_url(), pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_async_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

