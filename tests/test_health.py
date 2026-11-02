"""Health API tests."""

import asyncio

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from tests.fakes import FakeDatabase


async def request(app: FastAPI, path: str) -> Response:
    """Issue one request directly against the ASGI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def test_health_reports_service_metadata(app: FastAPI) -> None:
    response = asyncio.run(request(app, "/health"))

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "macromonitor",
        "version": "0.1.0",
        "environment": "test",
    }


def test_openapi_document_is_available(app: FastAPI) -> None:
    response = asyncio.run(request(app, "/openapi.json"))

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "MacroMonitor API"
    assert "/health" in response.json()["paths"]
    assert "/ready" in response.json()["paths"]


def test_readiness_reports_healthy_database(app: FastAPI) -> None:
    response = asyncio.run(request(app, "/ready"))

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "healthy"}


def test_readiness_reports_unavailable_database(
    app: FastAPI,
    database: FakeDatabase,
) -> None:
    database.available = False

    response = asyncio.run(request(app, "/ready"))

    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "database_unavailable"}}


def test_application_lifespan_disposes_database(
    app: FastAPI,
    database: FakeDatabase,
) -> None:
    async def run_lifespan() -> None:
        async with app.router.lifespan_context(app):
            assert database.disposed is False

    asyncio.run(run_lifespan())

    assert database.disposed is True
