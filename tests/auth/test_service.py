"""Authentication service behavior without an external database."""

from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest

from research_data_builder.auth import AuthenticationError, AuthService, DuplicateEmailError
from research_data_builder.auth.repository import AuthRepository
from research_data_builder.auth.security import hash_password, hash_session_token
from research_data_builder.db.models import User, UserSession


class MemoryAuthRepository:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.sessions: dict[str, UserSession] = {}

    async def get_user_by_email(self, email: str) -> User | None:
        return self.users.get(email)

    async def create_user(self, email: str, password_hash: str) -> User:
        user = User(
            id=uuid4(),
            email=email,
            password_hash=password_hash,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.users[email] = user
        return user

    async def create_session(
        self,
        user: User,
        token_hash: str,
        *,
        now: datetime,
        expires_at: datetime,
    ) -> UserSession:
        session = UserSession(
            id=uuid4(),
            user_id=user.id,
            user=user,
            token_hash=token_hash,
            last_used_at=now,
            expires_at=expires_at,
        )
        self.sessions[token_hash] = session
        return session

    async def get_active_session(self, token_hash: str, *, now: datetime) -> UserSession | None:
        session = self.sessions.get(token_hash)
        if session is None or session.revoked_at is not None or session.expires_at <= now:
            return None
        return session

    async def touch(self, session: UserSession, *, now: datetime) -> None:
        session.last_used_at = now

    async def revoke(self, token_hash: str, *, now: datetime) -> bool:
        session = self.sessions.get(token_hash)
        if session is None or session.revoked_at is not None:
            return False
        session.revoked_at = now
        return True


def service(repository: MemoryAuthRepository) -> AuthService:
    return AuthService(cast(AuthRepository, repository), session_ttl_hours=24)


@pytest.mark.anyio
async def test_registration_normalizes_email_and_stores_only_token_hash() -> None:
    repository = MemoryAuthRepository()
    result = await service(repository).register("  Researcher@Example.COM ", "a secure password")

    assert result.user.email == "researcher@example.com"
    assert result.user.password_hash != "a secure password"
    assert hash_session_token(result.token) in repository.sessions
    assert result.token not in repository.sessions

    with pytest.raises(DuplicateEmailError):
        await service(repository).register("RESEARCHER@example.com", "another password")


@pytest.mark.anyio
async def test_login_session_authentication_and_logout() -> None:
    repository = MemoryAuthRepository()
    registered = await service(repository).register("person@example.com", "a secure password")

    logged_in = await service(repository).login("PERSON@example.com", "a secure password")
    assert logged_in.user.id == registered.user.id
    assert await service(repository).authenticate(logged_in.token) == registered.user
    assert await service(repository).logout(logged_in.token) is True

    with pytest.raises(AuthenticationError, match="authentication required"):
        await service(repository).authenticate(logged_in.token)


@pytest.mark.anyio
async def test_login_uses_one_generic_failure_for_missing_incorrect_or_inactive_users() -> None:
    repository = MemoryAuthRepository()
    user = User(
        id=uuid4(),
        email="inactive@example.com",
        password_hash=hash_password("a secure password"),
        is_active=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repository.users[user.email] = user

    for email, password in (
        ("missing@example.com", "a secure password"),
        ("inactive@example.com", "wrong password"),
        ("inactive@example.com", "a secure password"),
    ):
        with pytest.raises(AuthenticationError, match="invalid email or password"):
            await service(repository).login(email, password)
