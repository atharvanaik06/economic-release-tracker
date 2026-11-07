"""Authentication endpoint behavior and secure cookie policy."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from research_data_builder.api.auth import Credentials, current_user, login, logout, register
from research_data_builder.core.config import Settings
from research_data_builder.db.models import User, UserSession


class TransactionContext:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_: object) -> None:
        return None


class FakeAuthDatabase:
    def __init__(self, session: MagicMock) -> None:
        self.session_value = session

    @asynccontextmanager
    async def session(self) -> AsyncIterator[MagicMock]:
        yield self.session_value


def auth_session(*scalar_values: object) -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    session.scalar = AsyncMock(side_effect=list(scalar_values))
    session.flush = AsyncMock()
    session.begin.return_value = TransactionContext()

    def assign_defaults(model: object) -> None:
        if isinstance(model, User):
            model.id = model.id or uuid4()
            model.is_active = True
            model.created_at = datetime.now(UTC)
            model.updated_at = datetime.now(UTC)
        if isinstance(model, UserSession):
            model.id = model.id or uuid4()

    session.add.side_effect = assign_defaults
    return session


def request_for(
    session: MagicMock,
    *,
    cookies: dict[str, str] | None = None,
    environment: str = "test",
) -> Request:
    settings = Settings(environment=environment, _env_file=None)  # type: ignore[arg-type,call-arg]
    state = SimpleNamespace(database=FakeAuthDatabase(session), settings=settings)
    return cast(
        Request,
        SimpleNamespace(
            app=SimpleNamespace(state=state),
            cookies=cookies or {},
        ),
    )


@pytest.mark.anyio
async def test_register_sets_http_only_session_cookie() -> None:
    response = Response()
    resource = await register(
        Credentials(email="Person@Example.com", password="a secure password"),
        request_for(auth_session(None)),
        response,
    )

    assert resource.email == "person@example.com"
    cookie = response.headers["set-cookie"]
    assert "research_data_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Secure" not in cookie


@pytest.mark.anyio
async def test_login_uses_generic_failure_and_production_cookie_is_secure() -> None:
    user = User(
        id=uuid4(),
        email="person@example.com",
        password_hash="malformed",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    with pytest.raises(HTTPException) as failed:
        await login(
            Credentials(email=user.email, password="a secure password"),
            request_for(auth_session(user)),
            Response(),
        )
    assert failed.value.status_code == 401
    assert failed.value.detail == "invalid email or password"

    from research_data_builder.auth.security import hash_password

    user.password_hash = hash_password("a secure password")
    response = Response()
    await login(
        Credentials(email=user.email, password="a secure password"),
        request_for(auth_session(user), environment="production"),
        response,
    )
    assert "Secure" in response.headers["set-cookie"]


@pytest.mark.anyio
async def test_current_user_requires_active_cookie_session_and_logout_revokes_it() -> None:
    user = User(
        id=uuid4(),
        email="person@example.com",
        password_hash="stored-hash",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    stored_session = UserSession(
        id=uuid4(),
        user_id=user.id,
        user=user,
        token_hash="a" * 64,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        last_used_at=datetime.now(UTC),
    )

    resource = await current_user(
        request_for(auth_session(stored_session), cookies={"research_data_session": "raw-token"})
    )
    assert resource.id == user.id

    response = Response()
    await logout(
        request_for(auth_session(stored_session), cookies={"research_data_session": "raw-token"}),
        response,
    )
    assert stored_session.revoked_at is not None
    assert "research_data_session=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]

    with pytest.raises(HTTPException) as missing:
        await current_user(request_for(auth_session(), cookies={}))
    assert missing.value.status_code == 401
