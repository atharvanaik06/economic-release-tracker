"""Tests for idempotent normalized provider catalog refresh."""

from typing import cast
from uuid import uuid4

import pytest

from research_data_builder.db.models import Series
from research_data_builder.db.repositories import SeriesInput, SeriesUpsertResult
from research_data_builder.providers import (
    DataProvider,
    Frequency,
    Indicator,
    ProviderCapabilities,
    ProviderConnector,
)
from research_data_builder.providers.catalog import ProviderCatalogService


class FakeConnector:
    provider = DataProvider.FRED
    capabilities = ProviderCapabilities(True, False, True, False, True)

    def __init__(self, indicators: list[Indicator]) -> None:
        self.indicators = indicators
        self.request: tuple[str, int] | None = None

    async def search_indicators(self, query: str, *, limit: int = 20) -> list[Indicator]:
        self.request = (query, limit)
        return self.indicators


class FakeCatalogStore:
    def __init__(self) -> None:
        self.inputs: list[SeriesInput] = []

    async def upsert(self, values: SeriesInput) -> SeriesUpsertResult:
        self.inputs.append(values)
        outcomes = {
            "CREATE": (True, False),
            "UPDATE": (False, True),
            "SAME": (False, False),
        }
        created, updated = outcomes[values.provider_series_id]
        series = Series(
            id=uuid4(),
            provider=values.provider,
            provider_series_id=values.provider_series_id,
            title=values.title,
            units=values.units,
            frequency=values.frequency,
            provider_metadata=values.provider_metadata,
            metadata_fingerprint=values.metadata_fingerprint,
        )
        return SeriesUpsertResult(series=series, created=created, updated=updated)


def make_indicator(indicator_id: str) -> Indicator:
    return Indicator(
        provider=DataProvider.FRED,
        provider_indicator_id=indicator_id,
        title=f"Indicator {indicator_id}",
        description="Description",
        unit=None,
        frequency=Frequency.MONTHLY,
        source_url=f"https://example.test/{indicator_id}",
        provider_metadata={"nested": {"value": 1}},
    )


@pytest.mark.anyio
async def test_catalog_refresh_deduplicates_fingerprints_and_counts_writes() -> None:
    connector = FakeConnector(
        [
            make_indicator("UPDATE"),
            make_indicator("CREATE"),
            make_indicator("SAME"),
            make_indicator("CREATE"),
        ]
    )
    store = FakeCatalogStore()
    service = ProviderCatalogService(cast(ProviderConnector, connector), store)

    summary = await service.refresh("output", limit=25)

    assert connector.request == ("output", 25)
    assert summary.discovered == 3
    assert summary.created == 1
    assert summary.updated == 1
    assert summary.unchanged == 1
    assert [item.provider_series_id for item in store.inputs] == ["CREATE", "SAME", "UPDATE"]
    assert all(len(item.metadata_fingerprint or "") == 64 for item in store.inputs)
    assert store.inputs[0].frequency == "monthly"
    assert store.inputs[0].units == ""
