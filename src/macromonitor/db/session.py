"""Asynchronous PostgreSQL engine and session management."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class DatabaseLifecycle(Protocol):
    """Database behavior required by the application lifecycle and readiness API."""

    async def check(self) -> None:
        """Raise when the database cannot execute a trivial query."""

    async def dispose(self) -> None:
        """Release database connection-pool resources."""


class Database:
    """Own the SQLAlchemy async engine and session factory."""

    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.engine: AsyncEngine = create_async_engine(url, echo=echo, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield one session without implicitly committing its work."""
        async with self.session_factory() as session:
            yield session

    async def check(self) -> None:
        """Verify that PostgreSQL accepts a simple query."""
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        """Close all pooled connections."""
        await self.engine.dispose()
