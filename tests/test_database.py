"""Database wrapper unit tests."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from research_data_builder.db.session import Database


class AsyncContext:
    """Minimal asynchronous context manager for database doubles."""

    def __init__(self, value: object) -> None:
        self.value = value

    async def __aenter__(self) -> object:
        return self.value

    async def __aexit__(self, *_: object) -> None:
        return None


def test_database_session_check_and_dispose() -> None:
    async def scenario() -> None:
        session = object()
        connection = AsyncMock()
        engine = MagicMock()
        engine.dispose = AsyncMock()
        engine.connect.return_value = AsyncContext(connection)

        database = object.__new__(Database)
        database.engine = engine
        database.session_factory = lambda: AsyncContext(session)  # type: ignore[assignment]

        async with database.session() as yielded:
            assert yielded is session

        await database.check()
        await database.dispose()

        connection.execute.assert_awaited_once()
        engine.dispose.assert_awaited_once()

    asyncio.run(scenario())
