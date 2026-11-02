"""Refresh normalized provider metadata into the PostgreSQL catalog."""

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from research_data_builder.db.repositories import SeriesInput, SeriesUpsertResult
from research_data_builder.providers.domain import Indicator
from research_data_builder.providers.protocol import ProviderConnector


class SeriesCatalogStore(Protocol):
    """Small persistence boundary needed by catalog refresh."""

    async def upsert(self, values: SeriesInput) -> SeriesUpsertResult:
        """Idempotently persist one provider indicator."""
        ...


@dataclass(frozen=True, slots=True)
class CatalogRefreshSummary:
    """Counts returned after one bounded provider catalog refresh."""

    provider: str
    discovered: int
    created: int
    updated: int
    unchanged: int


class ProviderCatalogService:
    """Coordinate connector search and idempotent catalog persistence."""

    def __init__(self, connector: ProviderConnector, store: SeriesCatalogStore) -> None:
        self.connector = connector
        self.store = store

    async def refresh(self, query: str, *, limit: int = 100) -> CatalogRefreshSummary:
        indicators = await self.connector.search_indicators(query, limit=limit)
        unique_indicators = {indicator.provider_indicator_id: indicator for indicator in indicators}

        created = 0
        updated = 0
        unchanged = 0
        for indicator_id in sorted(unique_indicators):
            result = await self.store.upsert(self._series_input(unique_indicators[indicator_id]))
            if result.created:
                created += 1
            elif result.updated:
                updated += 1
            else:
                unchanged += 1

        return CatalogRefreshSummary(
            provider=self.connector.provider.value,
            discovered=len(unique_indicators),
            created=created,
            updated=updated,
            unchanged=unchanged,
        )

    @classmethod
    def _series_input(cls, indicator: Indicator) -> SeriesInput:
        metadata = {
            "description": indicator.description,
            "source_url": indicator.source_url,
            "provider_payload": indicator.provider_metadata,
        }
        fingerprint_payload = {
            "provider": indicator.provider.value,
            "provider_indicator_id": indicator.provider_indicator_id,
            "title": indicator.title,
            "unit": indicator.unit,
            "frequency": indicator.frequency.value,
            "metadata": metadata,
        }
        canonical_json = json.dumps(
            fingerprint_payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        fingerprint = hashlib.sha256(canonical_json.encode()).hexdigest()
        return SeriesInput(
            provider=indicator.provider.value,
            provider_series_id=indicator.provider_indicator_id,
            title=indicator.title,
            units=indicator.unit or "",
            frequency=indicator.frequency.value,
            provider_metadata=metadata,
            metadata_fingerprint=fingerprint,
        )
