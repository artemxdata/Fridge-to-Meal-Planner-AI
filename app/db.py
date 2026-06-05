from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, echo=settings.database_echo)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
_schema_ready = False


async def get_session() -> AsyncIterator[AsyncSession]:
    await ensure_schema()
    async with SessionLocal() as session:
        yield session


async def create_schema() -> None:
    global _schema_ready
    from app.models import Base

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    _schema_ready = True


async def ensure_schema() -> None:
    if settings.auto_create_tables and not _schema_ready:
        await create_schema()


async def check_database() -> None:
    await ensure_schema()
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
