"""Contract implemented by every public-data provider connector."""

from typing import Protocol

from research_data_builder.providers.domain import (
    DataProvider,
    Entity,
    Indicator,
    Observation,
    ObservationQuery,
    ProviderCapabilities,
)


class ProviderConnector(Protocol):
    """Provider-neutral asynchronous connector contract."""

    provider: DataProvider
    capabilities: ProviderCapabilities

    async def search_indicators(self, query: str, *, limit: int = 20) -> list[Indicator]:
        """Find normalized indicators matching a human search term."""
        ...

    async def get_indicator(self, indicator_id: str) -> Indicator:
        """Return normalized metadata for one exact provider indicator."""
        ...

    async def list_entities(self) -> list[Entity]:
        """Return normalized geographic entities when supported."""
        ...

    async def get_observations(self, query: ObservationQuery) -> list[Observation]:
        """Return normalized, deterministically ordered observations."""
        ...
