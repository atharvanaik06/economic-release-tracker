"""Resolve frozen recipe variables into deterministic provider build plans."""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from research_data_builder.db.models import RecipeVersion
from research_data_builder.providers.domain import Indicator
from research_data_builder.providers.registry import ProviderRegistry
from research_data_builder.recipes.schemas import RecipeDefinition, VariableDefinition


@dataclass(frozen=True, slots=True)
class ResolvedBuildInput:
    """One exact normalized provider request in a build plan."""

    output_name: str
    provider: str
    indicator_id: str
    request: dict[str, Any]
    indicator_metadata: dict[str, Any]
    indicator_fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "output_name": self.output_name,
            "provider": self.provider,
            "indicator_id": self.indicator_id,
            "request": self.request,
            "indicator_metadata": self.indicator_metadata,
            "indicator_fingerprint": self.indicator_fingerprint,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ResolvedBuildInput":
        return cls(
            output_name=str(payload["output_name"]),
            provider=str(payload["provider"]),
            indicator_id=str(payload["indicator_id"]),
            request=dict(payload["request"]),
            indicator_metadata=dict(payload["indicator_metadata"]),
            indicator_fingerprint=str(payload["indicator_fingerprint"]),
        )


@dataclass(frozen=True, slots=True)
class BuildPlan:
    """Content-addressed execution plan for one immutable recipe version."""

    recipe_version_id: str
    recipe_content_hash: str
    build_identity: str
    planner_version: str
    inputs: tuple[ResolvedBuildInput, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "recipe_version_id": self.recipe_version_id,
            "recipe_content_hash": self.recipe_content_hash,
            "build_identity": self.build_identity,
            "planner_version": self.planner_version,
            "inputs": [item.as_dict() for item in self.inputs],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BuildPlan":
        return cls(
            recipe_version_id=str(payload["recipe_version_id"]),
            recipe_content_hash=str(payload["recipe_content_hash"]),
            build_identity=str(payload["build_identity"]),
            planner_version=str(payload["planner_version"]),
            inputs=tuple(ResolvedBuildInput.from_dict(dict(item)) for item in payload["inputs"]),
        )


class BuildPlanner:
    """Resolve provider metadata and create a stable plan identity."""

    planner_version = "1"

    def __init__(self, providers: ProviderRegistry) -> None:
        self.providers = providers

    async def plan(self, version: RecipeVersion) -> BuildPlan:
        definition = RecipeDefinition.model_validate(version.content)
        resolved: list[ResolvedBuildInput] = []
        for variable in definition.variables:
            resolved.append(await self._resolve_variable(definition, variable))

        identity_payload = {
            "recipe_content_hash": version.content_hash,
            "planner_version": self.planner_version,
            "inputs": [item.as_dict() for item in resolved],
        }
        build_identity = self._fingerprint(identity_payload)
        return BuildPlan(
            recipe_version_id=str(version.id),
            recipe_content_hash=version.content_hash,
            build_identity=build_identity,
            planner_version=self.planner_version,
            inputs=tuple(resolved),
        )

    async def _resolve_variable(
        self,
        definition: RecipeDefinition,
        variable: VariableDefinition,
    ) -> ResolvedBuildInput:
        connector = self.providers.get(variable.provider)
        indicator = await connector.get_indicator(variable.indicator_id)
        if indicator.provider is not variable.provider:
            raise ValueError("connector returned an indicator for the wrong provider")

        entity_ids = (
            list(definition.entities) if connector.capabilities.geographic_filtering else []
        )
        request = {
            "indicator_id": variable.indicator_id,
            "entity_ids": entity_ids,
            "start_date": definition.start_date.isoformat(),
            "end_date": definition.end_date.isoformat(),
        }
        normalized_metadata = self._indicator_metadata(indicator)
        return ResolvedBuildInput(
            output_name=variable.output_name,
            provider=variable.provider.value,
            indicator_id=variable.indicator_id,
            request=request,
            indicator_metadata=normalized_metadata,
            indicator_fingerprint=self._fingerprint(normalized_metadata),
        )

    @staticmethod
    def _indicator_metadata(indicator: Indicator) -> dict[str, Any]:
        return {
            "provider": indicator.provider.value,
            "provider_indicator_id": indicator.provider_indicator_id,
            "title": indicator.title,
            "description": indicator.description,
            "unit": indicator.unit,
            "frequency": indicator.frequency.value,
            "source_url": indicator.source_url,
            "provider_metadata": indicator.provider_metadata,
        }

    @staticmethod
    def _fingerprint(payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()
