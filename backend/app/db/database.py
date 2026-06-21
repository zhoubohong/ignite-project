"""Database engine and session management with pgvector support."""
from __future__ import annotations

from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

_engine_kwargs = {}
if not settings.database_url.startswith("sqlite"):
    _engine_kwargs = {"pool_size": 10, "max_overflow": 20}

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    **_engine_kwargs,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session


_is_sqlite = settings.database_url.startswith("sqlite")


async def init_db() -> None:
    """Create tables and enable pgvector extension (PostgreSQL) or shim types (SQLite)."""
    from app.models.base import Base  # noqa: F811

    if _is_sqlite:
        _shim_pg_types()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _shim_pg_types() -> None:
    """Replace PostgreSQL-only column types (ARRAY, JSONB, Vector) with SQLite equivalents."""
    from sqlalchemy import JSON, LargeBinary, ARRAY
    from sqlalchemy.dialects.postgresql import JSONB
    from pgvector.sqlalchemy import Vector
    from app.models.base import Base

    # Force model imports to register tables
    import app.models.user  # noqa: F401
    import app.models.question  # noqa: F401
    import app.models.session  # noqa: F401

    for table in list(Base.metadata.tables.values()):
        for col in table.columns:
            new_type = None
            if hasattr(col.type, "item_type") or isinstance(col.type, ARRAY):
                new_type = JSON()
            elif isinstance(col.type, JSONB):
                new_type = JSON()
            elif isinstance(col.type, Vector):
                new_type = LargeBinary()
            if new_type is not None:
                col.type = new_type
