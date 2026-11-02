"""Configured provider connector registry."""

from collections.abc import Iterable

from research_data_builder.providers.domain import DataProvider, ProviderCapabilities
from research_data_builder.providers.errors import ProviderConfigurationError
from research_data_builder.providers.protocol import ProviderConnector


class ProviderRegistry:
    """Resolve configured connectors without provider-specific conditionals."""

    def __init__(self, connectors: Iterable[ProviderConnector]) -> None:
        self._connectors: dict[DataProvider, ProviderConnector] = {}
        for connector in connectors:
            if connector.provider in self._connectors:
                raise ProviderConfigurationError(
                    f"duplicate connector configured for {connector.provider.value}"
                )
            self._connectors[connector.provider] = connector

    def get(self, provider: DataProvider) -> ProviderConnector:
        """Return a configured connector or an actionable configuration failure."""
        try:
            return self._connectors[provider]
        except KeyError as error:
            raise ProviderConfigurationError(
                f"provider connector is not configured: {provider.value}"
            ) from error

    def providers(self) -> tuple[DataProvider, ...]:
        """Return configured provider names in stable order."""
        return tuple(sorted(self._connectors, key=lambda provider: provider.value))

    def capabilities(self) -> dict[DataProvider, ProviderCapabilities]:
        """Expose immutable capability metadata for planning and UI code."""
        return {provider: self._connectors[provider].capabilities for provider in self.providers()}
