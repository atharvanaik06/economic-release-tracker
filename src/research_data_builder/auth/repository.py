"""Persistence operations for researcher accounts and browser sessions."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from research_data_builder.db.models import User, UserSession


class AuthRepository:
    """Store accounts and hashed, revocable session tokens without committing."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email))

    async def create_user(self, email: str, password_hash: str) -> User:
        user = User(email=email, password_hash=password_hash)
        self.session.add(user)
        await self.session.flush()
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
            user=user,
            token_hash=token_hash,
            last_used_at=now,
            expires_at=expires_at,
        )
        self.session.add(session)
        await self.session.flush()
        return session

    async def get_active_session(self, token_hash: str, *, now: datetime) -> UserSession | None:
        statement = (
            select(UserSession)
            .options(selectinload(UserSession.user))
            .where(
                UserSession.token_hash == token_hash,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
        )
        return await self.session.scalar(statement)

    async def touch(self, session: UserSession, *, now: datetime) -> None:
        session.last_used_at = now
        await self.session.flush()

    async def revoke(self, token_hash: str, *, now: datetime) -> bool:
        session = await self.session.scalar(
            select(UserSession).where(
                UserSession.token_hash == token_hash,
                UserSession.revoked_at.is_(None),
            )
        )
        if session is None:
            return False
        session.revoked_at = now
        await self.session.flush()
        return True
