"""Transactional repository operations for economic history."""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from research_data_builder.db.models import (
    ChangeEvent,
    ChangeType,
    ObservationVersion,
    Series,
    SyncRun,
    SyncStatus,
)


@dataclass(frozen=True, slots=True)
class SeriesInput:
    """Values required to register an economic series."""

    provider: str
    provider_series_id: str
    title: str
    units: str
    frequency: str
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    metadata_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class SeriesUpsertResult:
    """Outcome of idempotently writing one provider catalog entry."""

    series: Series
    created: bool
    updated: bool


@dataclass(frozen=True, slots=True)
class ObservationVersionInput:
    """Values required to append an observation version."""

    series_id: UUID
    sync_run_id: UUID
    observation_date: date
    value: Decimal | None
    is_missing: bool
    content_fingerprint: str
    realtime_start: date | None = None
    realtime_end: date | None = None
    first_observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class SyncCounts:
    """Summary counts recorded when a synchronization succeeds."""

    new: int = 0
    revised: int = 0
    unchanged: int = 0
    removed: int = 0
    missing: int = 0


@dataclass(frozen=True, slots=True)
class ChangeEventInput:
    """Values required to persist one immutable change event."""

    series_id: UUID
    sync_run_id: UUID
    change_type: ChangeType
    deterministic_key: str
    observation_date: date | None = None
    previous_version_id: UUID | None = None
    new_version_id: UUID | None = None
    change_amount: Decimal | None = None
    absolute_change: Decimal | None = None
    metadata_changes: dict[str, Any] | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class SeriesRepository:
    """Persist and retrieve tracked economic series."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, values: SeriesInput) -> Series:
        series = Series(
            provider=values.provider,
            provider_series_id=values.provider_series_id,
            title=values.title,
            units=values.units,
            frequency=values.frequency,
            provider_metadata=values.provider_metadata,
            metadata_fingerprint=values.metadata_fingerprint,
        )
        self.session.add(series)
        await self.session.flush()
        return series

    async def get_by_provider_id(self, provider: str, provider_series_id: str) -> Series | None:
        statement = select(Series).where(
            Series.provider == provider,
            Series.provider_series_id == provider_series_id,
        )
        return await self.session.scalar(statement)

    async def upsert(self, values: SeriesInput) -> SeriesUpsertResult:
        """Create, update, or leave unchanged one normalized provider series."""
        existing = await self.get_by_provider_id(values.provider, values.provider_series_id)
        if existing is None:
            created = await self.create(values)
            return SeriesUpsertResult(series=created, created=True, updated=False)

        if existing.metadata_fingerprint == values.metadata_fingerprint:
            return SeriesUpsertResult(series=existing, created=False, updated=False)

        existing.title = values.title
        existing.units = values.units
        existing.frequency = values.frequency
        existing.provider_metadata = values.provider_metadata
        existing.metadata_fingerprint = values.metadata_fingerprint
        existing.active = True
        await self.session.flush()
        return SeriesUpsertResult(series=existing, created=False, updated=True)


class SyncRunRepository:
    """Manage synchronization audit records without committing transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def start(self, series_id: UUID) -> SyncRun:
        run = SyncRun(series_id=series_id, status=SyncStatus.RUNNING)
        self.session.add(run)
        await self.session.flush()
        return run

    async def succeed(self, run: SyncRun, counts: SyncCounts) -> SyncRun:
        run.status = SyncStatus.SUCCEEDED
        run.finished_at = datetime.now(UTC)
        run.new_count = counts.new
        run.revised_count = counts.revised
        run.unchanged_count = counts.unchanged
        run.removed_count = counts.removed
        run.missing_count = counts.missing
        await self.session.flush()
        return run

    async def fail(self, run: SyncRun, *, error_code: str, error_message: str) -> SyncRun:
        run.status = SyncStatus.FAILED
        run.finished_at = datetime.now(UTC)
        run.error_code = error_code
        run.error_message = error_message
        await self.session.flush()
        return run


class ObservationVersionRepository:
    """Append and query immutable observation versions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append(self, values: ObservationVersionInput) -> ObservationVersion:
        version = ObservationVersion(
            series_id=values.series_id,
            sync_run_id=values.sync_run_id,
            observation_date=values.observation_date,
            value=values.value,
            is_missing=values.is_missing,
            realtime_start=values.realtime_start,
            realtime_end=values.realtime_end,
            first_observed_at=values.first_observed_at,
            content_fingerprint=values.content_fingerprint,
        )
        self.session.add(version)
        await self.session.flush()
        return version

    async def get_by_fingerprint(self, fingerprint: str) -> ObservationVersion | None:
        return await self.session.scalar(
            select(ObservationVersion).where(ObservationVersion.content_fingerprint == fingerprint)
        )

    async def latest_for_period(
        self,
        series_id: UUID,
        observation_date: date,
    ) -> ObservationVersion | None:
        statement = self._period_statement(series_id, observation_date).order_by(
            ObservationVersion.first_observed_at.desc(),
            ObservationVersion.id.desc(),
        )
        return await self.session.scalar(statement.limit(1))

    async def list_for_period(
        self,
        series_id: UUID,
        observation_date: date,
    ) -> list[ObservationVersion]:
        statement = self._period_statement(series_id, observation_date).order_by(
            ObservationVersion.first_observed_at,
            ObservationVersion.id,
        )
        result = await self.session.scalars(statement)
        return list(result)

    @staticmethod
    def _period_statement(series_id: UUID, observation_date: date) -> Select[ObservationVersion]:
        return select(ObservationVersion).where(
            ObservationVersion.series_id == series_id,
            ObservationVersion.observation_date == observation_date,
        )


class ChangeEventRepository:
    """Persist and query immutable economic change events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, values: ChangeEventInput) -> ChangeEvent:
        event = ChangeEvent(
            series_id=values.series_id,
            sync_run_id=values.sync_run_id,
            change_type=values.change_type,
            observation_date=values.observation_date,
            previous_version_id=values.previous_version_id,
            new_version_id=values.new_version_id,
            change_amount=values.change_amount,
            absolute_change=values.absolute_change,
            metadata_changes=values.metadata_changes,
            deterministic_key=values.deterministic_key,
            occurred_at=values.occurred_at,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_for_sync_run(self, sync_run_id: UUID) -> list[ChangeEvent]:
        result = await self.session.scalars(
            select(ChangeEvent)
            .where(ChangeEvent.sync_run_id == sync_run_id)
            .order_by(ChangeEvent.occurred_at, ChangeEvent.id)
        )
        return list(result)
