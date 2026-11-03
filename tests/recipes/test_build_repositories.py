"""Tests for idempotent build-plan persistence."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from research_data_builder.db.build_repositories import BuildRepository
from research_data_builder.db.models import BuildInput, BuildStatus
from research_data_builder.recipes.planner import BuildPlan, ResolvedBuildInput


def build_plan() -> BuildPlan:
    item = ResolvedBuildInput(
        output_name="gdp_growth",
        provider="world_bank",
        indicator_id="NY.GDP.MKTP.KD.ZG",
        request={"entity_ids": ["CZE"]},
        indicator_metadata={"title": "GDP growth"},
        indicator_fingerprint="a" * 64,
    )
    return BuildPlan(
        recipe_version_id=str(uuid4()),
        recipe_content_hash="b" * 64,
        build_identity="c" * 64,
        planner_version="1",
        inputs=(item,),
    )


@pytest.mark.anyio
async def test_build_repository_persists_plan_and_resolved_inputs() -> None:
    session = MagicMock(spec=AsyncSession)
    session.scalar = AsyncMock(return_value=None)
    session.flush = AsyncMock()
    repository = BuildRepository(session)

    result = await repository.create_or_get(uuid4(), build_plan())

    assert result.created is True
    assert result.build.status is BuildStatus.PLANNED
    added = [call.args[0] for call in session.add.call_args_list]
    inputs = [item for item in added if isinstance(item, BuildInput)]
    assert inputs[0].output_name == "gdp_growth"
    assert session.flush.await_count == 2


@pytest.mark.anyio
async def test_build_repository_reuses_existing_identity() -> None:
    session = MagicMock(spec=AsyncSession)
    existing = MagicMock()
    session.scalar = AsyncMock(return_value=existing)
    session.flush = AsyncMock()

    result = await BuildRepository(session).create_or_get(uuid4(), build_plan())

    assert result.created is False
    assert result.build is existing
    session.add.assert_not_called()
