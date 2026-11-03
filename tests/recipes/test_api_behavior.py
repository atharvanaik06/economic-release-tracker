"""Behavioral tests for recipe and deterministic build API operations."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from research_data_builder.api.recipes import (
    create_recipe,
    export_recipe_version,
    freeze_recipe,
    get_build,
    get_recipe,
    get_recipe_version,
    import_recipe,
    list_recipe_versions,
    list_recipes,
    plan_build,
    update_recipe,
)
from research_data_builder.db.models import BuildRun, BuildStatus, DatasetRecipe, RecipeVersion
from research_data_builder.providers import (
    DataProvider,
    Frequency,
    Indicator,
    ProviderCapabilities,
    ProviderConnector,
    ProviderRegistry,
)
from research_data_builder.recipes.codec import canonical_recipe_hash
from research_data_builder.recipes.schemas import RecipeDefinition
from tests.recipes.test_schemas import valid_recipe


class TransactionContext:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_: object) -> None:
        return None


def session_with(*scalar_values: object) -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.scalar = AsyncMock(side_effect=list(scalar_values))
    session.scalars = AsyncMock()
    session.begin.return_value = TransactionContext()

    def assign_id(model: Any) -> None:
        if hasattr(model, "id") and model.id is None:
            model.id = uuid4()

    session.add.side_effect = assign_id
    return session


class FakeApiDatabase:
    def __init__(self, *sessions: MagicMock) -> None:
        self.sessions = iter(sessions)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[MagicMock]:
        yield next(self.sessions)


class ApiConnector:
    provider = DataProvider.WORLD_BANK
    capabilities = ProviderCapabilities(True, True, True, True)

    async def get_indicator(self, indicator_id: str) -> Indicator:
        return Indicator(
            provider=self.provider,
            provider_indicator_id=indicator_id,
            title=f"Indicator {indicator_id}",
            description="Fixture",
            unit="percent",
            frequency=Frequency.ANNUAL,
            source_url="https://example.test",
        )


def api_request(database: FakeApiDatabase, *, registry: ProviderRegistry | None = None) -> Request:
    state = SimpleNamespace(
        database=database,
        provider_registry=registry or ProviderRegistry([]),
    )
    return cast(Request, SimpleNamespace(app=SimpleNamespace(state=state)))


def stored_recipe(definition: RecipeDefinition) -> DatasetRecipe:
    return DatasetRecipe(
        id=uuid4(),
        name=definition.name,
        description=definition.description,
        draft_content=definition.model_dump(mode="json"),
        draft_hash=canonical_recipe_hash(definition),
    )


def stored_version(recipe: DatasetRecipe, definition: RecipeDefinition) -> RecipeVersion:
    return RecipeVersion(
        id=uuid4(),
        recipe_id=recipe.id,
        version_number=1,
        content=definition.model_dump(mode="json"),
        content_hash=canonical_recipe_hash(definition),
    )


@pytest.mark.anyio
async def test_recipe_api_creates_imports_reads_lists_and_updates_drafts() -> None:
    definition = RecipeDefinition.model_validate(valid_recipe())

    created = await create_recipe(definition, api_request(FakeApiDatabase(session_with())))
    assert created.name == "European macro panel"

    imported = await import_recipe(
        api_request(FakeApiDatabase(session_with())),
        document="""
name: Imported
entities: [CZE]
start_date: 2020-01-01
end_date: 2021-12-31
variables:
  - provider: world_bank
    indicator_id: SP.POP.TOTL
    output_name: population
output_frequency: annual
""",
        format="yaml",
    )
    assert imported.name == "Imported"

    recipe = stored_recipe(definition)
    fetched = await get_recipe(recipe.id, api_request(FakeApiDatabase(session_with(recipe))))
    assert fetched.id == recipe.id

    scalar_result = MagicMock()
    scalar_result.__iter__.return_value = iter([recipe])
    list_session = session_with()
    list_session.scalars.return_value = scalar_result
    listed = await list_recipes(api_request(FakeApiDatabase(list_session)))
    assert [item.id for item in listed] == [recipe.id]

    updated_definition = definition.model_copy(update={"name": "Updated"})
    updated = await update_recipe(
        recipe.id,
        updated_definition,
        api_request(FakeApiDatabase(session_with(recipe))),
    )
    assert updated.name == "Updated"

    with pytest.raises(HTTPException) as invalid_import:
        await import_recipe(api_request(FakeApiDatabase()), document="not: [valid", format="yaml")
    assert invalid_import.value.status_code == 422


@pytest.mark.anyio
async def test_recipe_api_freezes_lists_and_exports_versions() -> None:
    definition = RecipeDefinition.model_validate(valid_recipe())
    recipe = stored_recipe(definition)
    freeze_session = session_with(recipe, None, 0)

    frozen = await freeze_recipe(
        recipe.id,
        api_request(FakeApiDatabase(freeze_session)),
        Response(),
    )
    assert frozen.version_number == 1

    version = stored_version(recipe, definition)
    fetched = await get_recipe_version(
        version.id, api_request(FakeApiDatabase(session_with(version)))
    )
    assert fetched.content_hash == version.content_hash

    scalar_result = MagicMock()
    scalar_result.__iter__.return_value = iter([version])
    list_session = session_with(recipe)
    list_session.scalars.return_value = scalar_result
    versions = await list_recipe_versions(recipe.id, api_request(FakeApiDatabase(list_session)))
    assert [item.id for item in versions] == [version.id]

    exported = await export_recipe_version(
        version.id,
        api_request(FakeApiDatabase(session_with(version))),
        format="json",
    )
    assert exported.media_type == "application/json"
    assert b'"name": "European macro panel"' in exported.body


@pytest.mark.anyio
async def test_build_api_resolves_persists_reuses_and_reads_plans() -> None:
    definition = RecipeDefinition.model_validate(valid_recipe())
    recipe = stored_recipe(definition)
    version = stored_version(recipe, definition)
    registry = ProviderRegistry([cast(ProviderConnector, ApiConnector())])

    planned = await plan_build(
        version.id,
        api_request(FakeApiDatabase(session_with(version), session_with(None)), registry=registry),
        Response(),
    )
    assert planned.status == "planned"
    assert len(planned.build_identity) == 64

    build = BuildRun(
        id=uuid4(),
        recipe_version_id=version.id,
        status=BuildStatus.PLANNED,
        build_identity="a" * 64,
        plan={"inputs": []},
    )
    fetched = await get_build(build.id, api_request(FakeApiDatabase(session_with(build))))
    assert fetched.id == build.id


@pytest.mark.anyio
async def test_recipe_api_returns_not_found_errors() -> None:
    missing_id = uuid4()
    with pytest.raises(HTTPException) as missing_recipe:
        await get_recipe(missing_id, api_request(FakeApiDatabase(session_with(None))))
    assert missing_recipe.value.status_code == 404

    with pytest.raises(HTTPException) as missing_version:
        await get_recipe_version(missing_id, api_request(FakeApiDatabase(session_with(None))))
    assert missing_version.value.status_code == 404

    with pytest.raises(HTTPException) as missing_build:
        await get_build(missing_id, api_request(FakeApiDatabase(session_with(None))))
    assert missing_build.value.status_code == 404
