"""Reusable FastAPI authentication boundary for protected resources."""

from fastapi import HTTPException, Request, status

from research_data_builder.auth.repository import AuthRepository
from research_data_builder.auth.service import AuthenticationError, AuthService
from research_data_builder.core.config import Settings
from research_data_builder.db.models import User
from research_data_builder.db.session import Database


async def require_user(request: Request) -> User:
    """Resolve the active researcher for an opaque session cookie."""
    database: Database = request.app.state.database
    settings: Settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required"
        )
    async with database.session() as session, session.begin():
        try:
            return await AuthService(
                AuthRepository(session), session_ttl_hours=settings.session_ttl_hours
            ).authenticate(token)
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="authentication required",
            ) from error
