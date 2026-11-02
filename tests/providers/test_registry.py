"""Tests for configured provider discovery."""

from typing import cast

import pytest

from research_data_builder.providers import DataProvider, ProviderCapabilities, ProviderConnector
from research_data_builder.providers.errors import ProviderConfigurationError
from research_data_builder.providers.registry import ProviderRegistry


class ConnectorStub:
    def __init__(self, provider: DataProvider) -> None:
        self.provider = provider
        self.capabilities = ProviderCapabilities(True, False, True, False)


def connector(provider: DataProvider) -> ProviderConnector:
    return cast(ProviderConnector, ConnectorStub(provider))


def test_registry_resolves_connectors_and_capabilities_in_stable_order() -> None:
    world_bank = connector(DataProvider.WORLD_BANK)
    fred = connector(DataProvider.FRED)
    registry = ProviderRegistry([world_bank, fred])

    assert registry.providers() == (DataProvider.FRED, DataProvider.WORLD_BANK)
    assert registry.get(DataProvider.FRED) is fred
    assert registry.capabilities()[DataProvider.WORLD_BANK].indicator_search is True


def test_registry_rejects_duplicates_and_reports_missing_configuration() -> None:
    fred = connector(DataProvider.FRED)
    with pytest.raises(ProviderConfigurationError, match="duplicate"):
        ProviderRegistry([fred, fred])

    registry = ProviderRegistry([fred])
    with pytest.raises(ProviderConfigurationError, match="world_bank"):
        registry.get(DataProvider.WORLD_BANK)
