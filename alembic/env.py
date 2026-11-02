"""Alembic environment for asynchronous PostgreSQL migrations."""

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from research_data_builder.core.config import get_settings  # noqa: E402
from research_data_builder.db import models  # noqa: E402, F401
from research_data_builder.db.base import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without creating an Engine."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def configure_and_run(connection: Connection) -> None:
    """Configure an online migration against one synchronous connection proxy."""
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and execute migrations."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(configure_and_run)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations with an asynchronous PostgreSQL driver."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
