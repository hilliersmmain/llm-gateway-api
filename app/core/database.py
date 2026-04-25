"""Async database configuration with SQLModel."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.core.config import get_settings
from app.models.log import GuardrailLog, RequestLog

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.log_level == "DEBUG",
    future=True,
)

async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def cleanup_old_logs(retention_days: int) -> None:
    """Best-effort cleanup for old log records."""
    if retention_days <= 0:
        return
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=retention_days)
    async with async_session() as session:
        await session.execute(delete(RequestLog).where(RequestLog.timestamp < cutoff))
        await session.execute(delete(GuardrailLog).where(GuardrailLog.timestamp < cutoff))
        await session.commit()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
