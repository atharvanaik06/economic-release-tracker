"""Tests for provider resolution and deterministic build identity."""

from typing import cast
from uuid import uuid4

import pytest

from research_data_builder.db.models import RecipeVersion
from research_data_builder.providers import (
    DataProvider,
    Frequency,
    Indicator,
    ProviderCapabilities,
    ProviderConnector,
    ProviderRegistry,
)
from research_data_builder.recipes.codec import canonical_recipe_hash
from research_data_builder.recipes.planner import BuildPlanner
from research_data_builder.recipes.schemas import RecipeDefinition
from tests.recipes.test_schemas import valid_recipe


class IndicatorConnector:
    provider = DataProvider.WORLD_BANK
    capabilities = ProviderCapabilities(True, True, True, True)

    def __init__(self, title_suffix: str = "") -> None:
        self.title_suffix = title_suffix
        self.requested: list[str] = []

    async def get_indicator(self, indicator_id: str) -> Indicator:
        self.requested.append(indicator_id)
        return Indicator(
            provider=self.provider,
            provider_indicator_id=indicator_id,
            title=f"Indicator {indicator_id}{self.title_suffix}",
            description="Provider description",
            unit="percent",
            frequency=Frequency.ANNUAL,
            source_url=f"https://example.test/{indicator_id}",
            provider_metadata={"source": "fixture"},
        )


def frozen_version(definition: RecipeDefinition) -> RecipeVersion:
    return RecipeVersion(
        id=uuid4(),
        recipe_id=uuid4(),
        version_number=1,
        content=definition.model_dump(mode="json"),
        content_hash=canonical_recipe_hash(definition),
    )


@pytest.mark.anyio
async def test_planner_resolves_requests_and_is_deterministic() -> None:
    definition = RecipeDefinition.model_validate(valid_recipe())
    connector = IndicatorConnector()
    planner = BuildPlanner(ProviderRegistry([cast(ProviderConnector, connector)]))
    version = frozen_version(definition)

    first = await planner.plan(version)
    second = await planner.plan(version)

    assert first.build_identity == second.build_identity
    assert len(first.build_identity) == 64
    assert [item.output_name for item in first.inputs] == ["gdp_growth", "inflation"]
    assert first.inputs[0].request["entity_ids"] == ["CZE", "DEU"]
    assert first.inputs[0].request["start_date"] == "2000-01-01"


@pytest.mark.anyio
async def test_planner_identity_changes_when_resolved_metadata_changes() -> None:
    definition = RecipeDefinition.model_validate(valid_recipe())
    version = frozen_version(definition)
    original = BuildPlanner(ProviderRegistry([cast(ProviderConnector, IndicatorConnector())]))
    changed = BuildPlanner(
        ProviderRegistry([cast(ProviderConnector, IndicatorConnector(" revised"))])
    )

    assert (await original.plan(version)).build_identity != (
        await changed.plan(version)
    ).build_identity
