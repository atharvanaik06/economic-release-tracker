"""Persistence for validated, lineage-complete export bundles."""

from datetime import UTC, datetime
from typing import ClassVar
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from research_data_builder.artifacts.models import BundleResult
from research_data_builder.db.models import (
    BuildLineage,
    BuildRun,
    BuildStatus,
    DatasetValidationResult,
    ExportArtifact,
)
from research_data_builder.validation.models import ValidationReport


class BuildOutputRepository:
    """Atomically replace one build's output metadata and mark it successful."""

    REQUIRED_DOCUMENTS: ClassVar[frozenset[str]] = frozenset(
        {
            "recipe.yaml",
            "validation.json",
            "validation.md",
            "codebook.json",
            "citations.md",
            "lineage.json",
            "manifest.json",
            "checksums.sha256",
        }
    )

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_success(
        self,
        build: BuildRun,
        bundle: BundleResult,
        validation: ValidationReport,
    ) -> BuildRun:
        if not validation.passed:
            raise ValueError("cannot succeed a build with validation errors")
        artifact_names = {artifact.name for artifact in bundle.artifacts}
        if not self.REQUIRED_DOCUMENTS.issubset(artifact_names):
            raise ValueError("required research-bundle artifacts are missing")

        for model in (DatasetValidationResult, BuildLineage, ExportArtifact):
            await self.session.execute(delete(model).where(model.build_run_id == build.id))

        for issue in validation.issues:
            self.session.add(
                DatasetValidationResult(
                    build_run_id=build.id,
                    code=issue.code,
                    severity=issue.severity,
                    variable=issue.variable,
                    message=issue.message,
                    details=issue.details,
                )
            )
        self.session.add(BuildLineage(build_run_id=build.id, content=bundle.lineage))
        for artifact in bundle.artifacts:
            self.session.add(
                ExportArtifact(
                    build_run_id=build.id,
                    name=artifact.name,
                    kind=artifact.kind,
                    relative_path=artifact.relative_path,
                    size_bytes=artifact.size_bytes,
                    sha256=artifact.sha256,
                )
            )
        build.status = BuildStatus.SUCCEEDED
        build.finished_at = datetime.now(UTC)
        build.dataset_checksum = bundle.dataset_checksum
        build.bundle_path = f"builds/{build.id}"
        await self.session.flush()
        return build

    async def list_validation(self, build_id: UUID) -> list[DatasetValidationResult]:
        rows = await self.session.scalars(
            select(DatasetValidationResult)
            .where(DatasetValidationResult.build_run_id == build_id)
            .order_by(DatasetValidationResult.created_at, DatasetValidationResult.id)
        )
        return list(rows)

    async def get_lineage(self, build_id: UUID) -> BuildLineage | None:
        return await self.session.scalar(
            select(BuildLineage).where(BuildLineage.build_run_id == build_id)
        )

    async def list_exports(self, build_id: UUID) -> list[ExportArtifact]:
        rows = await self.session.scalars(
            select(ExportArtifact)
            .where(ExportArtifact.build_run_id == build_id)
            .order_by(ExportArtifact.name)
        )
        return list(rows)

    async def get_export(self, export_id: UUID) -> ExportArtifact | None:
        return await self.session.scalar(
            select(ExportArtifact).where(ExportArtifact.id == export_id)
        )
