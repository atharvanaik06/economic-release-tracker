"""Account registration, credential verification, and session lifecycle."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from research_data_builder.auth.repository import AuthRepository
from research_data_builder.auth.security import (
    hash_password,
    hash_session_token,
    new_session_token,
    verify_password,
)
from research_data_builder.db.models import User

DUMMY_PASSWORD_HASH = hash_password("constant-time-login-placeholder", salt=b"\0" * 16)


class DuplicateEmailError(ValueError):
    """Raised when registration uses an existing normalized email."""


class AuthenticationError(ValueError):
    """Raised for invalid credentials or sessions without revealing which field failed."""


@dataclass(frozen=True)
class AuthResult:
    user: User
    token: str
    expires_at: datetime


class AuthService:
    """Coordinate password and session security around transactional repositories."""

    def __init__(self, repository: AuthRepository, *, session_ttl_hours: int) -> None:
        self.repository = repository
        self.session_ttl = timedelta(hours=session_ttl_hours)

    async def register(self, email: str, password: str) -> AuthResult:
        normalized_email = normalize_email(email)
        if await self.repository.get_user_by_email(normalized_email) is not None:
            raise DuplicateEmailError("an account with this email already exists")
        user = await self.repository.create_user(normalized_email, hash_password(password))
        return await self._start_session(user)

    async def login(self, email: str, password: str) -> AuthResult:
        normalized_email = normalize_email(email)
        user = await self.repository.get_user_by_email(normalized_email)
        encoded_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
        valid = verify_password(password, encoded_hash)
        if user is None or not valid or not user.is_active:
            raise AuthenticationError("invalid email or password")
        return await self._start_session(user)

    async def authenticate(self, token: str) -> User:
        now = datetime.now(UTC)
        session = await self.repository.get_active_session(hash_session_token(token), now=now)
        if session is None or not session.user.is_active:
            raise AuthenticationError("authentication required")
        await self.repository.touch(session, now=now)
        return session.user

    async def logout(self, token: str) -> bool:
        return await self.repository.revoke(
            hash_session_token(token),
            now=datetime.now(UTC),
        )

    async def _start_session(self, user: User) -> AuthResult:
        now = datetime.now(UTC)
        expires_at = now + self.session_ttl
        token = new_session_token()
        await self.repository.create_session(
            user,
            hash_session_token(token),
            now=now,
            expires_at=expires_at,
        )
        return AuthResult(user=user, token=token, expires_at=expires_at)


def normalize_email(email: str) -> str:
    """Use one stable representation for identity lookup and uniqueness."""
    return email.strip().casefold()
