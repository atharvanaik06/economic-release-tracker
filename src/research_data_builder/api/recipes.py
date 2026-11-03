"""Versioned recipe and deterministic build-plan HTTP API."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Query, Request, Response, status
from pydantic import BaseModel

from research_data_builder.db.build_repositories import BuildRepository
from research_data_builder.db.models import BuildRun, DatasetRecipe, RecipeVersion
from research_data_builder.db.recipe_repositories import RecipeRepository, RecipeVersionRepository
from research_data_builder.db.session import Database
from research_data_builder.providers.errors import ProviderConfigurationError, ProviderError
from research_data_builder.providers.registry import ProviderRegistry
from research_data_builder.recipes.codec import RecipeCodec
from research_data_builder.recipes.planner import BuildPlanner
from research_data_builder.recipes.schemas import RecipeDefinition
from research_data_builder.recipes.service import RecipeNotFoundError, RecipeService

router = APIRouter(prefix="/api/v1", tags=["recipes"])


class RecipeResource(BaseModel):
    id: UUID
    name: str
    description: str | None
    draft: RecipeDefinition
    draft_hash: str


class RecipeVersionResource(BaseModel):
    id: UUID
    recipe_id: UUID
    version_number: int
    content: RecipeDefinition
    content_hash: str


class BuildResource(BaseModel):
    id: UUID
    recipe_version_id: UUID
    status: str
    build_identity: str
    plan: dict[str, object]


def recipe_resource(recipe: DatasetRecipe) -> RecipeResource:
    return RecipeResource(
        id=recipe.id,
        name=recipe.name,
        description=recipe.description,
        draft=RecipeDefinition.model_validate(recipe.draft_content),
        draft_hash=recipe.draft_hash,
    )


def version_resource(version: RecipeVersion) -> RecipeVersionResource:
    return RecipeVersionResource(
        id=version.id,
        recipe_id=version.recipe_id,
        version_number=version.version_number,
        content=RecipeDefinition.model_validate(version.content),
        content_hash=version.content_hash,
    )


def build_resource(build: BuildRun) -> BuildResource:
    return BuildResource(
        id=build.id,
        recipe_version_id=build.recipe_version_id,
        status=build.status.value,
        build_identity=build.build_identity,
        plan=build.plan,
    )


@router.post("/recipes", response_model=RecipeResource, status_code=status.HTTP_201_CREATED)
async def create_recipe(definition: RecipeDefinition, request: Request) -> RecipeResource:
    database: Database = request.app.state.database
    async with database.session() as session, session.begin():
        recipe = await RecipeRepository(session).create(definition)
        return recipe_resource(recipe)


@router.post(
    "/recipes/import",
    response_model=RecipeResource,
    status_code=status.HTTP_201_CREATED,
)
async def import_recipe(
    request: Request,
    document: Annotated[str, Body(media_type="text/plain")],
    format: Annotated[Literal["json", "yaml"], Query()] = "yaml",
) -> RecipeResource:
    try:
        definition = (
            RecipeCodec.from_yaml(document) if format == "yaml" else RecipeCodec.from_json(document)
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
    return await create_recipe(definition, request)


@router.get("/recipes", response_model=list[RecipeResource])
async def list_recipes(request: Request) -> list[RecipeResource]:
    database: Database = request.app.state.database
    async with database.session() as session:
        recipes = await RecipeRepository(session).list()
        return [recipe_resource(recipe) for recipe in recipes]


@router.get("/recipes/{recipe_id}", response_model=RecipeResource)
async def get_recipe(recipe_id: UUID, request: Request) -> RecipeResource:
    database: Database = request.app.state.database
    async with database.session() as session:
        recipe = await RecipeRepository(session).get(recipe_id)
        if recipe is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="recipe not found")
        return recipe_resource(recipe)


@router.put("/recipes/{recipe_id}/draft", response_model=RecipeResource)
async def update_recipe(
    recipe_id: UUID,
    definition: RecipeDefinition,
    request: Request,
) -> RecipeResource:
    database: Database = request.app.state.database
    async with database.session() as session, session.begin():
        service = RecipeService(RecipeRepository(session), RecipeVersionRepository(session))
        try:
            recipe = await service.update(recipe_id, definition)
        except RecipeNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        return recipe_resource(recipe)


@router.post(
    "/recipes/{recipe_id}/versions",
    response_model=RecipeVersionResource,
    status_code=status.HTTP_201_CREATED,
)
async def freeze_recipe(
    recipe_id: UUID,
    request: Request,
    response: Response,
) -> RecipeVersionResource:
    database: Database = request.app.state.database
    async with database.session() as session, session.begin():
        service = RecipeService(RecipeRepository(session), RecipeVersionRepository(session))
        try:
            result = await service.freeze(recipe_id)
        except RecipeNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        if not result.created:
            response.status_code = status.HTTP_200_OK
        return version_resource(result.version)


@router.get("/recipe-versions/{version_id}", response_model=RecipeVersionResource)
async def get_recipe_version(version_id: UUID, request: Request) -> RecipeVersionResource:
    database: Database = request.app.state.database
    async with database.session() as session:
        version = await RecipeVersionRepository(session).get(version_id)
        if version is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="version not found")
        return version_resource(version)


@router.get("/recipes/{recipe_id}/versions", response_model=list[RecipeVersionResource])
async def list_recipe_versions(recipe_id: UUID, request: Request) -> list[RecipeVersionResource]:
    database: Database = request.app.state.database
    async with database.session() as session:
        recipe = await RecipeRepository(session).get(recipe_id)
        if recipe is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="recipe not found")
        versions = await RecipeVersionRepository(session).list_for_recipe(recipe_id)
        return [version_resource(version) for version in versions]


@router.get("/recipe-versions/{version_id}/export")
async def export_recipe_version(
    version_id: UUID,
    request: Request,
    format: Annotated[Literal["json", "yaml"], Query()] = "yaml",
) -> Response:
    database: Database = request.app.state.database
    async with database.session() as session:
        version = await RecipeVersionRepository(session).get(version_id)
        if version is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="version not found")
        definition = RecipeDefinition.model_validate(version.content)
        if format == "json":
            return Response(RecipeCodec.to_json(definition), media_type="application/json")
        return Response(RecipeCodec.to_yaml(definition), media_type="application/yaml")


@router.post(
    "/recipe-versions/{version_id}/builds",
    response_model=BuildResource,
    status_code=status.HTTP_201_CREATED,
)
async def plan_build(
    version_id: UUID,
    request: Request,
    response: Response,
) -> BuildResource:
    database: Database = request.app.state.database
    registry: ProviderRegistry = request.app.state.provider_registry

    async with database.session() as session:
        version = await RecipeVersionRepository(session).get(version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="version not found")

    try:
        plan = await BuildPlanner(registry).plan(version)
    except ProviderConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "provider_not_configured", "message": str(error)},
        ) from error
    except ProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "provider_resolution_failed", "message": str(error)},
        ) from error

    async with database.session() as session, session.begin():
        result = await BuildRepository(session).create_or_get(version.id, plan)
        if not result.created:
            response.status_code = status.HTTP_200_OK
        return build_resource(result.build)


@router.get("/builds/{build_id}", response_model=BuildResource)
async def get_build(build_id: UUID, request: Request) -> BuildResource:
    database: Database = request.app.state.database
    async with database.session() as session:
        build = await BuildRepository(session).get(build_id)
        if build is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="build not found")
        return build_resource(build)
