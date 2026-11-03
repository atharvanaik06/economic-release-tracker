"""Persistence for deterministic build plans and resolved provider inputs."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from research_data_builder.db.models import BuildInput, BuildRun, BuildStatus
from research_data_builder.recipes.planner import BuildPlan


@dataclass(frozen=True, slots=True)
class PlannedBuildResult:
    """A planned build plus whether it was newly persisted."""

    build: BuildRun
    created: bool


class BuildRepository:
    """Create or reuse deterministic build plans without committing transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_or_get(self, recipe_version_id: UUID, plan: BuildPlan) -> PlannedBuildResult:
        existing = await self.get_by_identity(plan.build_identity)
        if existing is not None:
            return PlannedBuildResult(build=existing, created=False)

        build = BuildRun(
            recipe_version_id=recipe_version_id,
            status=BuildStatus.PLANNED,
            build_identity=plan.build_identity,
            plan=plan.as_dict(),
        )
        self.session.add(build)
        await self.session.flush()
        for item in plan.inputs:
            self.session.add(
                BuildInput(
                    build_run_id=build.id,
                    output_name=item.output_name,
                    provider=item.provider,
                    indicator_id=item.indicator_id,
                    request=item.request,
                    indicator_metadata=item.indicator_metadata,
                    indicator_fingerprint=item.indicator_fingerprint,
                )
            )
        await self.session.flush()
        return PlannedBuildResult(build=build, created=True)

    async def get(self, build_id: UUID) -> BuildRun | None:
        return await self.session.scalar(select(BuildRun).where(BuildRun.id == build_id))

    async def get_by_identity(self, build_identity: str) -> BuildRun | None:
        return await self.session.scalar(
            select(BuildRun).where(BuildRun.build_identity == build_identity)
        )
