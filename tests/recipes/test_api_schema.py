"""API contract tests for recipe and build-planning routes."""

from fastapi import FastAPI


def test_recipe_and_build_routes_are_versioned_and_documented(app: FastAPI) -> None:
    schema = app.openapi()
    paths = schema["paths"]

    assert "/api/v1/recipes" in paths
    assert set(paths["/api/v1/recipes"]) == {"get", "post"}
    assert "/api/v1/recipes/import" in paths
    assert "/api/v1/recipes/{recipe_id}/draft" in paths
    assert "/api/v1/recipes/{recipe_id}/versions" in paths
    assert "/api/v1/recipe-versions/{version_id}/export" in paths
    assert "/api/v1/recipe-versions/{version_id}/builds" in paths
    assert "/api/v1/builds/{build_id}" in paths

    recipe_schema = schema["components"]["schemas"]["RecipeDefinition"]
    assert recipe_schema["additionalProperties"] is False
