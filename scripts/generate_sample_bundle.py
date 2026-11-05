"""Generate the deterministic checked-in Phase 6 sample research bundle."""

import asyncio
import hashlib
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID, uuid5

from research_data_builder.artifacts import export_research_bundle
from research_data_builder.db.models import RecipeVersion
from research_data_builder.engine.executor import BuildExecutor
from research_data_builder.providers import (
    DataProvider,
    Frequency,
    Observation,
    ObservationQuery,
    ProviderCapabilities,
    ProviderConnector,
    ProviderRegistry,
)
from research_data_builder.recipes.codec import canonical_recipe_hash
from research_data_builder.recipes.planner import BuildPlan, ResolvedBuildInput
from research_data_builder.recipes.schemas import RecipeDefinition
from research_data_builder.validation import validate_dataset

SAMPLE_BUILD_ID = UUID("11111111-1111-4111-8111-111111111111")


class SampleConnector:
    """Deterministic provider fixture used only for the published example."""

    provider = DataProvider.WORLD_BANK
    capabilities = ProviderCapabilities(True, True, True, True)

    async def get_observations(self, query: ObservationQuery) -> list[Observation]:
        fixture = {
            "NY.GDP.MKTP.KD.ZG": {"CZE": "2.8", "DEU": "0.3", "FRA": "1.1", "POL": "2.9"},
            "FP.CPI.TOTL.ZG": {"CZE": "10.7", "DEU": "5.9", "FRA": "4.9", "POL": "11.5"},
        }[query.indicator_id]
        return [
            Observation(
                provider=self.provider,
                indicator_id=query.indicator_id,
                entity_id=entity,
                period=date(2023, 12, 31),
                value=Decimal(value),
                is_missing=False,
                frequency=Frequency.ANNUAL,
            )
            for entity, value in fixture.items()
        ]


def recipe() -> RecipeDefinition:
    return RecipeDefinition.model_validate(
        {
            "name": "European macro panel sample",
            "description": "Deterministic fixture demonstrating the complete local MVP bundle.",
            "entities": ["CZE", "DEU", "FRA", "POL"],
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "variables": [
                {
                    "provider": "world_bank",
                    "indicator_id": "NY.GDP.MKTP.KD.ZG",
                    "output_name": "gdp_growth",
                },
                {
                    "provider": "world_bank",
                    "indicator_id": "FP.CPI.TOTL.ZG",
                    "output_name": "inflation",
                },
            ],
            "output_frequency": "annual",
            "join": {"type": "outer", "keys": ["entity", "period"]},
            "missing_values": "preserve",
            "formats": ["csv", "parquet"],
            "validations": [
                {
                    "variable": "inflation",
                    "minimum": -20,
                    "maximum": 100,
                    "severity": "error",
                }
            ],
        }
    )


def plan(definition: RecipeDefinition, version: RecipeVersion) -> BuildPlan:
    metadata = {
        "NY.GDP.MKTP.KD.ZG": ("GDP growth (annual %)", "percent"),
        "FP.CPI.TOTL.ZG": ("Inflation, consumer prices (annual %)", "percent"),
    }
    inputs = []
    for variable in definition.variables:
        title, unit = metadata[variable.indicator_id]
        inputs.append(
            ResolvedBuildInput(
                output_name=variable.output_name,
                provider=variable.provider.value,
                indicator_id=variable.indicator_id,
                request={
                    "indicator_id": variable.indicator_id,
                    "entity_ids": list(definition.entities),
                    "start_date": definition.start_date.isoformat(),
                    "end_date": definition.end_date.isoformat(),
                },
                indicator_metadata={
                    "title": title,
                    "unit": unit,
                    "frequency": "annual",
                    "source_url": f"https://data.worldbank.org/indicator/{variable.indicator_id}",
                },
                indicator_fingerprint=hashlib.sha256(
                    f"world_bank:{variable.indicator_id}:sample-v1".encode()
                ).hexdigest(),
            )
        )
    return BuildPlan(
        recipe_version_id=str(version.id),
        recipe_content_hash=version.content_hash,
        build_identity=canonical_recipe_hash(definition),
        planner_version="1",
        inputs=tuple(inputs),
    )


async def main() -> None:
    definition = recipe()
    content_hash = canonical_recipe_hash(definition)
    version = RecipeVersion(
        id=uuid5(SAMPLE_BUILD_ID, "recipe-version"),
        recipe_id=uuid5(SAMPLE_BUILD_ID, "recipe"),
        version_number=1,
        content=definition.model_dump(mode="json"),
        content_hash=content_hash,
    )
    resolved_plan = plan(definition, version)
    registry = ProviderRegistry([cast(ProviderConnector, SampleConnector())])
    result = await BuildExecutor(registry).execute(version, resolved_plan)
    validation = validate_dataset(result, definition)
    bundle = export_research_bundle(
        artifact_root=Path("examples/sample_bundle"),
        build_id=SAMPLE_BUILD_ID,
        build_identity=resolved_plan.build_identity,
        frame=result.frame,
        recipe=definition,
        plan=resolved_plan,
        validation=validation,
        entity_mapping_version=result.entity_mapping_version,
        application_version="0.1.0",
    )
    print(bundle.directory)


if __name__ == "__main__":
    asyncio.run(main())
