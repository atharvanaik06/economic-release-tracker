"""PostgreSQL integration tests for immutable recipes and build identity."""

import asyncio
import os
from typing import cast

import pytest
from sqlalchemy import delete

from research_data_builder.db.build_repositories import BuildRepository
from research_data_builder.db.models import (
    BuildInput,
    BuildRun,
    DatasetRecipe,
    RecipeVariable,
    RecipeVersion,
    TransformationStep,
)
from research_data_builder.db.recipe_repositories import RecipeRepository, RecipeVersionRepository
from research_data_builder.db.session import Database
from research_data_builder.providers import (
    DataProvider,
    Frequency,
    Indicator,
    ProviderCapabilities,
    ProviderConnector,
    ProviderRegistry,
)
from research_data_builder.recipes.planner import BuildPlanner
from research_data_builder.recipes.schemas import RecipeDefinition
from tests.recipes.test_schemas import valid_recipe

TEST_DATABASE_URL = os.getenv("RESEARCH_DATA_TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(TEST_DATABASE_URL is None, reason="PostgreSQL test URL is not configured"),
]


class FixtureConnector:
    provider = DataProvider.WORLD_BANK
    capabilities = ProviderCapabilities(True, True, True, True)

    async def get_indicator(self, indicator_id: str) -> Indicator:
        return Indicator(
            provider=self.provider,
            provider_indicator_id=indicator_id,
            title=f"Fixture {indicator_id}",
            description="Stable fixture metadata",
            unit="percent",
            frequency=Frequency.ANNUAL,
            source_url=f"https://example.test/{indicator_id}",
        )


async def clear_recipes(database: Database) -> None:
    async with database.session() as session, session.begin():
        for model in (
            BuildInput,
            BuildRun,
            TransformationStep,
            RecipeVariable,
            RecipeVersion,
            DatasetRecipe,
        ):
            await session.execute(delete(model))


def test_postgres_freezes_versions_and_reuses_deterministic_builds() -> None:
    async def scenario() -> None:
        assert TEST_DATABASE_URL is not None
        database = Database(TEST_DATABASE_URL)
        await clear_recipes(database)
        definition = RecipeDefinition.model_validate(valid_recipe())
        planner = BuildPlanner(ProviderRegistry([cast(ProviderConnector, FixtureConnector())]))

        try:
            async with database.session() as session, session.begin():
                recipes = RecipeRepository(session)
                versions = RecipeVersionRepository(session)
                recipe = await recipes.create(definition)
                frozen = await versions.freeze(recipe, definition)
                duplicate = await versions.freeze(recipe, definition)
                assert frozen.created is True
                assert duplicate.created is False
                assert duplicate.version.id == frozen.version.id
                version_id = frozen.version.id
                recipe_id = recipe.id

            async with database.session() as session:
                version = await RecipeVersionRepository(session).get(version_id)
                assert version is not None

            plan = await planner.plan(version)
            async with database.session() as session, session.begin():
                builds = BuildRepository(session)
                first = await builds.create_or_get(version_id, plan)
                second = await builds.create_or_get(version_id, plan)
                assert first.created is True
                assert second.created is False
                assert second.build.id == first.build.id

            changed = definition.model_copy(update={"name": "Changed draft"})
            async with database.session() as session, session.begin():
                stored_recipe = await RecipeRepository(session).get(recipe_id)
                assert stored_recipe is not None
                await RecipeRepository(session).update(stored_recipe, changed)

            async with database.session() as session:
                version = await RecipeVersionRepository(session).get(version_id)
                assert version is not None
                assert version.content["name"] == "European macro panel"
        finally:
            await database.dispose()

    asyncio.run(scenario())
