"""Contract and normalization tests for the FRED connector."""

from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest

from research_data_builder.providers import Frequency, ObservationQuery
from research_data_builder.providers.errors import (
    IndicatorNotFoundError,
    ProviderConfigurationError,
    ProviderResponseError,
    UnsupportedProviderOperationError,
)
from research_data_builder.providers.fred import FredConnector


def fred_series(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": "GDP",
        "title": "Gross Domestic Product",
        "notes": "Quarterly US output.",
        "units": "Billions of Dollars",
        "frequency": "Quarterly",
        "frequency_short": "Q",
    }
    return {**row, **overrides}


@pytest.mark.anyio
async def test_fred_search_and_exact_metadata_are_normalized() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"seriess": [fred_series()]})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.stlouisfed.org/fred"
    ) as client:
        connector = FredConnector(client, api_key="secret")
        search_result = await connector.search_indicators("gross domestic", limit=5)
        exact_result = await connector.get_indicator("GDP")

    assert search_result == [exact_result]
    assert exact_result.frequency is Frequency.QUARTERLY
    assert exact_result.unit == "Billions of Dollars"
    assert exact_result.source_url.endswith("/GDP")
    assert requests[0].url.path.endswith("/series/search")
    assert requests[0].url.params["search_text"] == "gross domestic"
    assert requests[0].url.params["api_key"] == "secret"


@pytest.mark.anyio
async def test_fred_observations_are_paginated_normalized_and_sorted() -> None:
    offsets: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/series"):
            return httpx.Response(200, json={"seriess": [fred_series()]})

        offsets.append(request.url.params["offset"])
        if request.url.params["offset"] == "0":
            return httpx.Response(
                200,
                json={
                    "count": 3,
                    "observations": [
                        {
                            "date": "2024-04-01",
                            "value": ".",
                            "realtime_start": "2024-07-01",
                            "realtime_end": "2024-07-01",
                        },
                        {
                            "date": "2024-01-01",
                            "value": "28624.069",
                            "realtime_start": "2024-07-01",
                            "realtime_end": "2024-07-01",
                        },
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "count": 3,
                "observations": [
                    {
                        "date": "2024-07-01",
                        "value": "29167.779",
                        "realtime_start": "2024-10-01",
                        "realtime_end": "2024-10-01",
                    }
                ],
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.stlouisfed.org/fred"
    ) as client:
        observations = await FredConnector(client, api_key="secret").get_observations(
            ObservationQuery(
                indicator_id="GDP",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
            )
        )

    assert offsets == ["0", "2"]
    assert [item.period for item in observations] == [
        date(2024, 1, 1),
        date(2024, 4, 1),
        date(2024, 7, 1),
    ]
    assert observations[0].value == Decimal("28624.069")
    assert observations[1].value is None
    assert observations[1].is_missing is True
    assert observations[2].frequency is Frequency.QUARTERLY


@pytest.mark.anyio
async def test_fred_reports_unsupported_entities_and_missing_indicators() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"seriess": []})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.stlouisfed.org/fred"
    ) as client:
        connector = FredConnector(client, api_key="secret")
        with pytest.raises(UnsupportedProviderOperationError):
            await connector.list_entities()
        with pytest.raises(UnsupportedProviderOperationError):
            await connector.get_observations(
                ObservationQuery(indicator_id="GDP", entity_ids=("US",))
            )
        with pytest.raises(IndicatorNotFoundError):
            await connector.get_indicator("UNKNOWN")


def test_fred_requires_configuration_and_valid_search_input() -> None:
    client = httpx.AsyncClient(base_url="https://api.stlouisfed.org/fred")
    try:
        with pytest.raises(ProviderConfigurationError):
            FredConnector(client, api_key=" ")
    finally:
        import asyncio

        asyncio.run(client.aclose())


@pytest.mark.anyio
async def test_fred_rejects_malformed_provider_values() -> None:
    call_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json={"seriess": [fred_series()]})
        return httpx.Response(
            200,
            json={"count": 1, "observations": [{"date": "not-a-date", "value": "not-a-number"}]},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.stlouisfed.org/fred"
    ) as client:
        with pytest.raises(ProviderResponseError):
            await FredConnector(client, api_key="secret").get_observations(
                ObservationQuery(indicator_id="GDP")
            )
