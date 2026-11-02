"""Create append-only economic history tables.

Revision ID: 0001
Revises: None
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the Phase 2 economic history schema."""
    op.create_table(
        "series",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_series_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("units", sa.String(length=128), nullable=False),
        sa.Column("frequency", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("provider_metadata", sa.JSON(), nullable=False),
        sa.Column("metadata_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("length(provider) > 0", name="provider_not_empty"),
        sa.CheckConstraint("length(provider_series_id) > 0", name="provider_series_id_not_empty"),
        sa.PrimaryKeyConstraint("id", name="pk_series"),
        sa.UniqueConstraint("provider", "provider_series_id", name="uq_series_provider_identity"),
    )

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("series_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "running",
                "succeeded",
                "failed",
                name="sync_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("new_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("revised_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("unchanged_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("removed_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("missing_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.CheckConstraint("new_count >= 0", name="new_count_nonnegative"),
        sa.CheckConstraint("revised_count >= 0", name="revised_count_nonnegative"),
        sa.CheckConstraint("unchanged_count >= 0", name="unchanged_count_nonnegative"),
        sa.CheckConstraint("removed_count >= 0", name="removed_count_nonnegative"),
        sa.CheckConstraint("missing_count >= 0", name="missing_count_nonnegative"),
        sa.CheckConstraint(
            "(status = 'running' AND finished_at IS NULL) OR "
            "(status IN ('succeeded', 'failed') AND finished_at IS NOT NULL)",
            name="status_matches_finished_at",
        ),
        sa.ForeignKeyConstraint(
            ["series_id"], ["series.id"], name="fk_sync_runs_series_id_series", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sync_runs"),
    )
    op.create_index(
        "ix_sync_runs_series_started", "sync_runs", ["series_id", "started_at"], unique=False
    )

    op.create_table(
        "observation_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("series_id", sa.Uuid(), nullable=False),
        sa.Column("sync_run_id", sa.Uuid(), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("is_missing", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("realtime_start", sa.Date(), nullable=True),
        sa.Column("realtime_end", sa.Date(), nullable=True),
        sa.Column(
            "first_observed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "(is_missing AND value IS NULL) OR (NOT is_missing AND value IS NOT NULL)",
            name="missing_matches_value",
        ),
        sa.ForeignKeyConstraint(
            ["series_id"],
            ["series.id"],
            name="fk_observation_versions_series_id_series",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sync_run_id"],
            ["sync_runs.id"],
            name="fk_observation_versions_sync_run_id_sync_runs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_observation_versions"),
        sa.UniqueConstraint("content_fingerprint", name="uq_observation_versions_fingerprint"),
    )
    op.create_index(
        "ix_observation_versions_series_period_observed",
        "observation_versions",
        ["series_id", "observation_date", "first_observed_at"],
        unique=False,
    )

    op.create_table(
        "change_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("series_id", sa.Uuid(), nullable=False),
        sa.Column("sync_run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "change_type",
            sa.Enum(
                "new",
                "revised",
                "removed",
                "missing",
                "metadata_changed",
                name="change_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("observation_date", sa.Date(), nullable=True),
        sa.Column("previous_version_id", sa.Uuid(), nullable=True),
        sa.Column("new_version_id", sa.Uuid(), nullable=True),
        sa.Column("change_amount", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("absolute_change", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("metadata_changes", sa.JSON(), nullable=True),
        sa.Column("deterministic_key", sa.String(length=64), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "change_type = 'metadata_changed' OR observation_date IS NOT NULL",
            name="observation_date_required",
        ),
        sa.CheckConstraint(
            "absolute_change IS NULL OR absolute_change >= 0",
            name="absolute_change_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["new_version_id"],
            ["observation_versions.id"],
            name="fk_change_events_new_version_id_observation_versions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_version_id"],
            ["observation_versions.id"],
            name="fk_change_events_previous_version_id_observation_versions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["series_id"],
            ["series.id"],
            name="fk_change_events_series_id_series",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sync_run_id"],
            ["sync_runs.id"],
            name="fk_change_events_sync_run_id_sync_runs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_change_events"),
        sa.UniqueConstraint("deterministic_key", name="uq_change_events_deterministic_key"),
    )
    op.create_index(
        "ix_change_events_series_occurred",
        "change_events",
        ["series_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the Phase 2 economic history schema."""
    op.drop_index("ix_change_events_series_occurred", table_name="change_events")
    op.drop_table("change_events")
    op.drop_index(
        "ix_observation_versions_series_period_observed", table_name="observation_versions"
    )
    op.drop_table("observation_versions")
    op.drop_index("ix_sync_runs_series_started", table_name="sync_runs")
    op.drop_table("sync_runs")
    op.drop_table("series")
