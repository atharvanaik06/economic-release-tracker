"""Reusable test doubles."""


class FakeDatabase:
    """Controllable database dependency for application tests."""

    def __init__(self) -> None:
        self.available = True
        self.disposed = False

    async def check(self) -> None:
        if not self.available:
            raise ConnectionError("test database unavailable")

    async def dispose(self) -> None:
        self.disposed = True
