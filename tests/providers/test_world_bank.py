"""Contract and normalization tests for the World Bank connector."""

from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest

from research_data_builder.providers import Frequency, ObservationQuery
from research_data_builder.providers.errors import IndicatorNotFoundError, ProviderResponseError
from research_data_builder.providers.world_bank import WorldBankConnector


def page(rows: list[dict[str, Any]], *, number: int = 1, pages: int = 1) -> list[Any]:
    return [{"page": number, "pages": pages, "total": len(rows)}, rows]


def indicator(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": "NY.GDP.MKTP.CD",
        "name": "GDP (current US$)",
        "unit": "US$",
        "sourceNote": "Gross domestic product at purchaser prices.",
        "source": {"id": "2", "value": "World Development Indicators"},
    }
    return {**row, **overrides}


@pytest.mark.anyio
async def test_world_bank_search_scans_pages_and_normalizes_metadata() -> None:
    requested_pages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_pages.append(request.url.params["page"])
        if request.url.params["page"] == "1":
            return httpx.Response(
                200,
                json=page(
                    [indicator(id="SP.POP.TOTL", name="Population", sourceNote="People")],
                    pages=2,
                ),
            )
        return httpx.Response(200, json=page([indicator()], number=2, pages=2))

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.worldbank.org/v2"
    ) as client:
        results = await WorldBankConnector(client).search_indicators("gross domestic", limit=10)

    assert requested_pages == ["1", "2"]
    assert len(results) == 1
    assert results[0].provider_indicator_id == "NY.GDP.MKTP.CD"
    assert results[0].frequency is Frequency.ANNUAL
    assert results[0].source_url.endswith("/NY.GDP.MKTP.CD")


@pytest.mark.anyio
async def test_world_bank_entities_are_paginated_and_normalized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["page"] == "1":
            return httpx.Response(
                200,
                json=page(
                    [
                        {
                            "id": "USA",
                            "iso2Code": "US",
                            "name": "United States",
                            "region": {"value": "North America"},
                            "incomeLevel": {"value": "High income"},
                        }
                    ],
                    pages=2,
                ),
            )
        return httpx.Response(
            200,
            json=page(
                [
                    {
                        "id": "DEU",
                        "iso2Code": "DE",
                        "name": "Germany",
                        "region": {"value": "Europe & Central Asia"},
                        "incomeLevel": {"value": "High income"},
                    }
                ],
                number=2,
                pages=2,
            ),
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.worldbank.org/v2"
    ) as client:
        entities = await WorldBankConnector(client).list_entities()

    assert [entity.provider_entity_id for entity in entities] == ["DEU", "USA"]
    assert entities[1].iso2_code == "US"
    assert entities[1].region == "North America"


@pytest.mark.anyio
async def test_world_bank_observations_apply_filters_and_normalize_missing_values() -> None:
    observation_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observation_request
        if request.url.path.removeprefix("/v2") == "/indicator/NY.GDP.MKTP.CD":
            return httpx.Response(200, json=page([indicator()]))
        observation_request = request
        return httpx.Response(
            200,
            json=page(
                [
                    {
                        "indicator": {"id": "NY.GDP.MKTP.CD"},
                        "country": {"id": "US", "value": "United States"},
                        "countryiso3code": "USA",
                        "date": "2023",
                        "value": 27360935200000,
                        "decimal": 0,
                        "obs_status": "",
                    },
                    {
                        "indicator": {"id": "NY.GDP.MKTP.CD"},
                        "country": {"id": "DE", "value": "Germany"},
                        "countryiso3code": "DEU",
                        "date": "2023",
                        "value": None,
                        "decimal": 0,
                        "obs_status": "",
                    },
                ]
            ),
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.worldbank.org/v2"
    ) as client:
        observations = await WorldBankConnector(client).get_observations(
            ObservationQuery(
                indicator_id="NY.GDP.MKTP.CD",
                entity_ids=("USA", "DEU"),
                start_date=date(2020, 6, 1),
                end_date=date(2023, 8, 1),
            )
        )

    assert observation_request is not None
    assert observation_request.url.path.endswith("/country/USA;DEU/indicator/NY.GDP.MKTP.CD")
    assert observation_request.url.params["date"] == "2020:2023"
    assert [item.entity_id for item in observations] == ["DEU", "USA"]
    assert observations[0].value is None
    assert observations[0].is_missing is True
    assert observations[1].value == Decimal("27360935200000")
    assert observations[1].period == date(2023, 1, 1)


@pytest.mark.anyio
async def test_world_bank_reports_missing_indicator_and_malformed_pages() -> None:
    responses: list[Any] = [page([]), {"not": "a page"}]

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=responses.pop(0))

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.worldbank.org/v2"
    ) as client:
        connector = WorldBankConnector(client)
        with pytest.raises(IndicatorNotFoundError):
            await connector.get_indicator("UNKNOWN")
        with pytest.raises(ProviderResponseError):
            await connector.list_entities()
