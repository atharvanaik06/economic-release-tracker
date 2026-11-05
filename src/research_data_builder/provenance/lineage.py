"""Source-to-output column lineage generation."""

from typing import Any

from research_data_builder.recipes.planner import BuildPlan
from research_data_builder.recipes.schemas import RecipeDefinition


def build_lineage(recipe: RecipeDefinition, plan: BuildPlan) -> dict[str, Any]:
    """Explain the provider source and ordered transformations for every output column."""
    inputs = {item.output_name: item for item in plan.inputs}
    columns: list[dict[str, Any]] = []
    for variable in recipe.variables:
        item = inputs[variable.output_name]
        metadata = item.indicator_metadata
        transformations = [
            {"operation": step.operation.value, "parameters": step.parameters}
            for step in recipe.transformations
            if step.variable == variable.output_name
        ]
        columns.append(
            {
                "output_column": variable.output_name,
                "provider": item.provider,
                "indicator_id": item.indicator_id,
                "title": metadata.get("title"),
                "source_unit": metadata.get("unit"),
                "source_frequency": metadata.get("frequency"),
                "source_url": metadata.get("source_url"),
                "request": item.request,
                "indicator_fingerprint": item.indicator_fingerprint,
                "transformations": transformations,
            }
        )
    return {
        "recipe_content_hash": plan.recipe_content_hash,
        "planner_version": plan.planner_version,
        "columns": columns,
    }
