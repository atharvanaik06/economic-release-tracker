"""Lifecycle-managed live provider clients for the application runtime."""

import httpx

from research_data_builder.core.config import Settings
from research_data_builder.providers.fred import FredConnector
from research_data_builder.providers.http import RetryPolicy
from research_data_builder.providers.protocol import ProviderConnector
from research_data_builder.providers.registry import ProviderRegistry
from research_data_builder.providers.world_bank import WorldBankConnector


class ProviderRuntime:
    """Own HTTP clients and expose configured connectors through one registry."""

    def __init__(self, settings: Settings) -> None:
        retry_policy = RetryPolicy(
            max_attempts=settings.provider_http_max_attempts,
            timeout_seconds=settings.provider_http_timeout_seconds,
        )
        self.clients: list[httpx.AsyncClient] = []

        world_bank_client = httpx.AsyncClient(
            base_url="https://api.worldbank.org/v2",
            headers={"User-Agent": f"{settings.app_name}/{settings.app_version}"},
        )
        self.clients.append(world_bank_client)
        connectors: list[ProviderConnector] = [
            WorldBankConnector(world_bank_client, retry_policy=retry_policy)
        ]

        if settings.fred_api_key is not None:
            fred_client = httpx.AsyncClient(
                base_url="https://api.stlouisfed.org/fred",
                headers={"User-Agent": f"{settings.app_name}/{settings.app_version}"},
            )
            self.clients.append(fred_client)
            connectors.append(
                FredConnector(
                    fred_client,
                    api_key=settings.fred_api_key.get_secret_value(),
                    retry_policy=retry_policy,
                )
            )
        self.registry = ProviderRegistry(connectors)

    async def close(self) -> None:
        """Close every provider connection pool."""
        for client in self.clients:
            await client.aclose()
