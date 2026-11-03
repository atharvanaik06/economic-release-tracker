"""Canonical JSON/YAML import, export, and hashing for recipes."""

import hashlib
import json
from typing import Any, cast

import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from research_data_builder.recipes.schemas import RecipeDefinition


def canonical_recipe_json(recipe: RecipeDefinition) -> str:
    """Serialize semantic recipe content with stable keys and separators."""
    return json.dumps(
        recipe.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def canonical_recipe_hash(recipe: RecipeDefinition) -> str:
    """Return the content address for a validated recipe."""
    return hashlib.sha256(canonical_recipe_json(recipe).encode()).hexdigest()


class RecipeCodec:
    """Safely import and export strict recipe documents."""

    @staticmethod
    def from_json(content: str) -> RecipeDefinition:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as error:
            raise ValueError("recipe is not valid JSON") from error
        return RecipeCodec._validate_mapping(payload)

    @staticmethod
    def from_yaml(content: str) -> RecipeDefinition:
        try:
            payload = yaml.safe_load(content)
        except yaml.YAMLError as error:
            raise ValueError("recipe is not valid YAML") from error
        return RecipeCodec._validate_mapping(payload)

    @staticmethod
    def to_json(recipe: RecipeDefinition) -> str:
        return json.dumps(recipe.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"

    @staticmethod
    def to_yaml(recipe: RecipeDefinition) -> str:
        return cast(
            str,
            yaml.safe_dump(
                recipe.model_dump(mode="json"),
                sort_keys=False,
                allow_unicode=True,
            ),
        )

    @staticmethod
    def _validate_mapping(payload: Any) -> RecipeDefinition:
        if not isinstance(payload, dict):
            raise ValueError("recipe document must contain an object")
        try:
            return RecipeDefinition.model_validate(payload)
        except ValidationError as error:
            raise ValueError(f"recipe validation failed: {error}") from error
