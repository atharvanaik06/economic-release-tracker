"""Health API tests."""

import asyncio

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response


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
