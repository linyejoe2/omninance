"""
db.py — PostgreSQL async engine and session factory.

Table models live in src/models/trading.py; data access lives in
src/repositories/. Schema is managed by alembic (migrations/) — init_db()
runs `alembic upgrade head` at startup so the container always boots on the
current schema.
"""
import asyncio
import logging
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/omninance"
)

engine = create_async_engine(DATABASE_URL, echo=False)

_ALEMBIC_INI = Path(__file__).parent.parent / "alembic.ini"


def get_session() -> AsyncSession:
    """New AsyncSession bound to the shared engine — use as `async with get_session() as session:`.

    expire_on_commit=False so ORM objects stay readable after commit — the
    default (True) makes any post-commit attribute access trigger a lazy sync
    load, which raises MissingGreenlet under asyncio.
    """
    return AsyncSession(engine, expire_on_commit=False)


def _run_migrations() -> None:
    """Blocking alembic upgrade — run in a thread."""
    config = Config(str(_ALEMBIC_INI))
    command.upgrade(config, "head")


async def init_db() -> None:
    await asyncio.to_thread(_run_migrations)
    logger.info("[DB] alembic upgrade head completed")
