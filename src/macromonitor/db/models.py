"""SQLAlchemy models for append-only economic observation history."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from macromonitor.db.base import Base


class SyncStatus(StrEnum):
    """Lifecycle states for one synchronization attempt."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ChangeType(StrEnum):
    """Meaningful changes emitted by the future revision engine."""

    NEW = "new"
    REVISED = "revised"
    REMOVED = "removed"
    MISSING = "missing"
    METADATA_CHANGED = "metadata_changed"


def enum_values(enum_type: type[StrEnum]) -> list[str]:
    """Persist string-enum values instead of Python member names."""
    return [member.value for member in enum_type]


class Series(Base):
    """One economic series tracked from an external provider."""

    __tablename__ = "series"
    __table_args__ = (
        UniqueConstraint("provider", "provider_series_id", name="uq_series_provider_identity"),
        CheckConstraint("length(provider) > 0", name="provider_not_empty"),
        CheckConstraint("length(provider_series_id) > 0", name="provider_series_id_not_empty"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(32))
    provider_series_id: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(255))
    units: Mapped[str] = mapped_column(String(128))
    frequency: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metadata_fingerprint: Mapped[str | None] = mapped_column(String(64))
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sync_runs: Mapped[list["SyncRun"]] = relationship(back_populates="series")
    observation_versions: Mapped[list["ObservationVersion"]] = relationship(back_populates="series")
    change_events: Mapped[list["ChangeEvent"]] = relationship(back_populates="series")


class SyncRun(Base):
    """Audit record for one attempt to synchronize a series."""

    __tablename__ = "sync_runs"
    __table_args__ = (
        CheckConstraint("new_count >= 0", name="new_count_nonnegative"),
        CheckConstraint("revised_count >= 0", name="revised_count_nonnegative"),
        CheckConstraint("unchanged_count >= 0", name="unchanged_count_nonnegative"),
        CheckConstraint("removed_count >= 0", name="removed_count_nonnegative"),
        CheckConstraint("missing_count >= 0", name="missing_count_nonnegative"),
        CheckConstraint(
            "(status = 'running' AND finished_at IS NULL) OR "
            "(status IN ('succeeded', 'failed') AND finished_at IS NOT NULL)",
            name="status_matches_finished_at",
        ),
        Index("ix_sync_runs_series_started", "series_id", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    series_id: Mapped[UUID] = mapped_column(
        ForeignKey("series.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[SyncStatus] = mapped_column(
        Enum(
            SyncStatus,
            name="sync_status",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
        ),
        default=SyncStatus.RUNNING,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    new_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    revised_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    unchanged_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    removed_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    missing_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(512))

    series: Mapped[Series] = relationship(back_populates="sync_runs")
    observation_versions: Mapped[list["ObservationVersion"]] = relationship(
        back_populates="sync_run"
    )
    change_events: Mapped[list["ChangeEvent"]] = relationship(back_populates="sync_run")


class ObservationVersion(Base):
    """Append-only version of one series value for one economic period."""

    __tablename__ = "observation_versions"
    __table_args__ = (
        UniqueConstraint("content_fingerprint", name="uq_observation_versions_fingerprint"),
        CheckConstraint(
            "(is_missing AND value IS NULL) OR (NOT is_missing AND value IS NOT NULL)",
            name="missing_matches_value",
        ),
        Index(
            "ix_observation_versions_series_period_observed",
            "series_id",
            "observation_date",
            "first_observed_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    series_id: Mapped[UUID] = mapped_column(
        ForeignKey("series.id", ondelete="RESTRICT"), nullable=False
    )
    sync_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("sync_runs.id", ondelete="RESTRICT"), nullable=False
    )
    observation_date: Mapped[date] = mapped_column(Date)
    value: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    is_missing: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    realtime_start: Mapped[date | None] = mapped_column(Date)
    realtime_end: Mapped[date | None] = mapped_column(Date)
    first_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    content_fingerprint: Mapped[str] = mapped_column(String(64))

    series: Mapped[Series] = relationship(back_populates="observation_versions")
    sync_run: Mapped[SyncRun] = relationship(back_populates="observation_versions")


class ChangeEvent(Base):
    """Immutable meaningful change produced by a synchronization run."""

    __tablename__ = "change_events"
    __table_args__ = (
        UniqueConstraint("deterministic_key", name="uq_change_events_deterministic_key"),
        CheckConstraint(
            "change_type = 'metadata_changed' OR observation_date IS NOT NULL",
            name="observation_date_required",
        ),
        CheckConstraint(
            "absolute_change IS NULL OR absolute_change >= 0",
            name="absolute_change_nonnegative",
        ),
        Index("ix_change_events_series_occurred", "series_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    series_id: Mapped[UUID] = mapped_column(
        ForeignKey("series.id", ondelete="RESTRICT"), nullable=False
    )
    sync_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("sync_runs.id", ondelete="RESTRICT"), nullable=False
    )
    change_type: Mapped[ChangeType] = mapped_column(
        Enum(
            ChangeType,
            name="change_type",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
        )
    )
    observation_date: Mapped[date | None] = mapped_column(Date)
    previous_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("observation_versions.id", ondelete="RESTRICT")
    )
    new_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("observation_versions.id", ondelete="RESTRICT")
    )
    change_amount: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    absolute_change: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    metadata_changes: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    deterministic_key: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    series: Mapped[Series] = relationship(back_populates="change_events")
    sync_run: Mapped[SyncRun] = relationship(back_populates="change_events")
    previous_version: Mapped[ObservationVersion | None] = relationship(
        foreign_keys=[previous_version_id]
    )
    new_version: Mapped[ObservationVersion | None] = relationship(foreign_keys=[new_version_id])
