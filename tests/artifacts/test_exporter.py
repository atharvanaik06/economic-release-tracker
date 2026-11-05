"""Tests for complete deterministic local research bundles."""

import json
from pathlib import Path
from typing import cast
from uuid import uuid4

import polars as pl
import pytest

from research_data_builder.artifacts import BundleResult, export_research_bundle
from research_data_builder.engine.executor import BuildExecutor
from research_data_builder.providers import ProviderConnector, ProviderRegistry
from research_data_builder.recipes.schemas import RecipeDefinition
from research_data_builder.validation import validate_dataset
from tests.engine.test_executor import ObservationConnector, version_and_plan


async def build_bundle(root: Path) -> BundleResult:
    version, plan = version_and_plan()
    registry = ProviderRegistry([cast(ProviderConnector, ObservationConnector())])
    result = await BuildExecutor(registry).execute(version, plan)
    recipe = RecipeDefinition.model_validate(version.content)
    report = validate_dataset(result, recipe)
    return export_research_bundle(
        artifact_root=root,
        build_id=uuid4(),
        build_identity=plan.build_identity,
        frame=result.frame,
        recipe=recipe,
        plan=plan,
        validation=report,
        entity_mapping_version=result.entity_mapping_version,
        application_version="0.1.0",
    )


@pytest.mark.anyio
async def test_exporter_writes_verified_csv_parquet_and_documentation(tmp_path: Path) -> None:
    bundle = await build_bundle(tmp_path)
    names = {artifact.name for artifact in bundle.artifacts}

    assert names == {
        "data.csv",
        "data.parquet",
        "recipe.yaml",
        "validation.json",
        "validation.md",
        "codebook.json",
        "citations.md",
        "lineage.json",
        "manifest.json",
        "checksums.sha256",
    }
    assert pl.read_parquet(bundle.directory / "data.parquet").height == 2
    assert (bundle.directory / "data.csv").read_text().startswith("entity,period")
    manifest = json.loads((bundle.directory / "manifest.json").read_text())
    assert manifest["dataset_checksum"] == bundle.dataset_checksum
    checksums = (bundle.directory / "checksums.sha256").read_text()
    assert "manifest.json" in checksums
    assert "checksums.sha256" not in checksums


@pytest.mark.anyio
async def test_exporter_rejects_blocking_validation_errors(tmp_path: Path) -> None:
    version, plan = version_and_plan()
    registry = ProviderRegistry([cast(ProviderConnector, ObservationConnector())])
    result = await BuildExecutor(registry).execute(version, plan)
    payload = dict(version.content)
    payload["validations"] = [{"variable": "gdp_growth", "maximum": 0, "severity": "error"}]
    recipe = RecipeDefinition.model_validate(payload)
    report = validate_dataset(result, recipe)

    with pytest.raises(ValueError, match="blocking"):
        export_research_bundle(
            artifact_root=tmp_path,
            build_id=uuid4(),
            build_identity=plan.build_identity,
            frame=result.frame,
            recipe=recipe,
            plan=plan,
            validation=report,
            entity_mapping_version=result.entity_mapping_version,
            application_version="0.1.0",
        )
