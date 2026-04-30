import re
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection
from sqlmodel import SQLModel

# Ensure all models are imported so their metadata is populated
import app.models.log  # noqa: F401
from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use SQLModel's shared metadata as the target for autogenerate.
target_metadata = SQLModel.metadata


def get_url() -> str:
    """Return the database URL, converting +asyncpg to +psycopg2 for the sync migration runner."""
    from app.core.config import get_settings

    url = get_settings().database_url or ""
    # Replace async driver with sync psycopg2 driver for Alembic's sync runner
    url = re.sub(r"\+asyncpg", "+psycopg2", url)
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine, though an
    Engine is acceptable here as well.  By skipping the Engine creation we
    don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a synchronous psycopg2 engine."""
    url = get_url()
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        do_run_migrations(connection)

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
