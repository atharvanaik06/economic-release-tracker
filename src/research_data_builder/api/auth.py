"""User registration, login, logout, and current-session HTTP API."""

import re
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from research_data_builder.auth import AuthenticationError, AuthService, DuplicateEmailError
from research_data_builder.auth.dependencies import require_user
from research_data_builder.auth.repository import AuthRepository
from research_data_builder.core.config import Settings
from research_data_builder.db.models import User
from research_data_builder.db.session import Database

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
Password = Annotated[str, StringConstraints(min_length=12, max_length=128)]


class Credentials(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: Password


class UserResource(BaseModel):
    id: UUID
    email: str
    is_active: bool
    created_at: datetime


def user_resource(user: User) -> UserResource:
    return UserResource.model_validate(user, from_attributes=True)


def validate_email(email: str) -> str:
    normalized = email.strip().casefold()
    if not EMAIL_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="email must be a valid address",
        )
    return normalized


def set_session_cookie(
    response: Response,
    result_token: str,
    settings: Settings,
) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=result_token,
        max_age=settings.session_ttl_hours * 60 * 60,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=UserResource, status_code=status.HTTP_201_CREATED)
async def register(credentials: Credentials, request: Request, response: Response) -> UserResource:
    database: Database = request.app.state.database
    settings: Settings = request.app.state.settings
    try:
        async with database.session() as session, session.begin():
            result = await AuthService(
                AuthRepository(session), session_ttl_hours=settings.session_ttl_hours
            ).register(validate_email(credentials.email), credentials.password)
    except (DuplicateEmailError, IntegrityError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="an account with this email already exists",
        ) from error
    set_session_cookie(response, result.token, settings)
    return user_resource(result.user)


@router.post("/login", response_model=UserResource)
async def login(credentials: Credentials, request: Request, response: Response) -> UserResource:
    database: Database = request.app.state.database
    settings: Settings = request.app.state.settings
    async with database.session() as session, session.begin():
        try:
            result = await AuthService(
                AuthRepository(session), session_ttl_hours=settings.session_ttl_hours
            ).login(validate_email(credentials.email), credentials.password)
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid email or password",
            ) from error
    set_session_cookie(response, result.token, settings)
    return user_resource(result.user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response) -> None:
    database: Database = request.app.state.database
    settings: Settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        async with database.session() as session, session.begin():
            await AuthService(
                AuthRepository(session), session_ttl_hours=settings.session_ttl_hours
            ).logout(token)
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.get("/me", response_model=UserResource)
async def current_user(request: Request) -> UserResource:
    return user_resource(await require_user(request))
