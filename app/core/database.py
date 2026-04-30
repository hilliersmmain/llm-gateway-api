"""Async database configuration with SQLModel."""

import asyncio
import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

from alembic.config import Config as AlembicConfig
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from alembic import command as alembic_command
from app.core.config import get_settings
from app.models.log import GuardrailLog, RequestLog

settings = get_settings()

# settings.database_url is guaranteed non-None by the model_validator at startup
assert settings.database_url is not None, "DATABASE_URL must be set before engine creation"

# When DB_POOL_DISABLED=1, use NullPool so asyncpg connections are never cached
# across event loops. This is required in tests where pytest-asyncio and
# Starlette's TestClient each run the app in their own asyncio loop — a pooled
# connection bound to one loop will raise RuntimeError in the other.
_pool_disabled = os.getenv("DB_POOL_DISABLED", "").lower() in ("1", "true", "yes")

if _pool_disabled:
    engine = create_async_engine(
        settings.database_url,
        echo=settings.log_level == "DEBUG",
        future=True,
        poolclass=NullPool,
    )
else:
    engine = create_async_engine(
        settings.database_url,
        echo=settings.log_level == "DEBUG",
        future=True,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def _run_alembic_upgrade() -> None:
    """Run 'alembic upgrade head' synchronously (called via asyncio.to_thread)."""
    alembic_cfg = AlembicConfig("alembic.ini")
    alembic_command.upgrade(alembic_cfg, "head")


async def init_db() -> None:
    """Apply all pending Alembic migrations to bring the schema up to head."""
    await asyncio.to_thread(_run_alembic_upgrade)


async def cleanup_old_logs(retention_days: int) -> None:
    """Best-effort cleanup for old log records."""
    if retention_days <= 0:
        return
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=retention_days)
    async with async_session() as session:
        await session.execute(delete(RequestLog).where(RequestLog.timestamp < cutoff))  # type: ignore[arg-type]  # SQLAlchemy __lt__ returns ColumnElement, not bool
        await session.execute(delete(GuardrailLog).where(GuardrailLog.timestamp < cutoff))  # type: ignore[arg-type]  # same
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
