"""Tests for strict recipe validation and stable serialization."""

import json

import pytest
from pydantic import ValidationError

from research_data_builder.recipes import RecipeCodec, RecipeDefinition, canonical_recipe_hash


def valid_recipe() -> dict[str, object]:
    return {
        "name": "European macro panel",
        "description": "Annual research inputs",
        "entities": ["CZE", "DEU"],
        "start_date": "2000-01-01",
        "end_date": "2025-12-31",
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
        "transformations": [
            {"operation": "lag", "variable": "inflation", "parameters": {"periods": 1}}
        ],
        "join": {"type": "outer", "keys": ["entity", "period"]},
        "missing_values": "preserve",
        "formats": ["csv", "parquet"],
    }


def test_recipe_round_trips_json_and_yaml_with_stable_hash() -> None:
    recipe = RecipeDefinition.model_validate(valid_recipe())

    from_json = RecipeCodec.from_json(RecipeCodec.to_json(recipe))
    from_yaml = RecipeCodec.from_yaml(RecipeCodec.to_yaml(recipe))

    assert from_json == recipe
    assert from_yaml == recipe
    assert canonical_recipe_hash(from_json) == canonical_recipe_hash(from_yaml)
    assert len(canonical_recipe_hash(recipe)) == 64


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ({"start_date": "2026-01-01"}, "start_date"),
        ({"entities": []}, "World Bank"),
        ({"formats": []}, "formats"),
        ({"unexpected": True}, "Extra inputs"),
    ],
)
def test_recipe_rejects_invalid_semantics(change: dict[str, object], match: str) -> None:
    payload = {**valid_recipe(), **change}
    with pytest.raises(ValidationError, match=match):
        RecipeDefinition.model_validate(payload)


def test_recipe_rejects_duplicate_outputs_and_unknown_transformation_variables() -> None:
    payload = valid_recipe()
    variables_value = payload["variables"]
    assert isinstance(variables_value, list)
    variables = list(variables_value)
    assert isinstance(variables[1], dict)
    variables[1] = {**variables[1], "output_name": "gdp_growth"}
    payload["variables"] = variables
    with pytest.raises(ValidationError, match="output_name"):
        RecipeDefinition.model_validate(payload)

    payload = valid_recipe()
    payload["transformations"] = [{"operation": "lag", "variable": "unknown"}]
    with pytest.raises(ValidationError, match="selected variable"):
        RecipeDefinition.model_validate(payload)


def test_recipe_codec_rejects_unsafe_or_non_object_documents() -> None:
    with pytest.raises(ValueError, match="valid JSON"):
        RecipeCodec.from_json("{")
    with pytest.raises(ValueError, match="object"):
        RecipeCodec.from_yaml("- one\n- two")
    with pytest.raises(ValueError, match="validation failed"):
        RecipeCodec.from_json(json.dumps({"name": "incomplete"}))
