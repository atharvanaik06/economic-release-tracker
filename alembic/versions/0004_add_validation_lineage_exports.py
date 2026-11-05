"""Add validation, lineage, exports, and successful bundle identity.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create durable Phase 6 validation, provenance, and export metadata."""
    op.add_column("build_runs", sa.Column("dataset_checksum", sa.String(64), nullable=True))
    op.add_column("build_runs", sa.Column("bundle_path", sa.String(512), nullable=True))
    op.create_table(
        "validation_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("build_run_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("variable", sa.String(128), nullable=True),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["build_run_id"],
            ["build_runs.id"],
            name="fk_validation_results_build_run_id_build_runs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_validation_results"),
    )
    op.create_table(
        "build_lineage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("build_run_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["build_run_id"],
            ["build_runs.id"],
            name="fk_build_lineage_build_run_id_build_runs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_build_lineage"),
        sa.UniqueConstraint("build_run_id", name="uq_build_lineage_build"),
    )
    op.create_table(
        "exports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("build_run_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("relative_path", sa.String(512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("size_bytes >= 0", name="export_size_nonnegative"),
        sa.CheckConstraint("length(sha256) = 64", name="export_sha256_length"),
        sa.ForeignKeyConstraint(
            ["build_run_id"],
            ["build_runs.id"],
            name="fk_exports_build_run_id_build_runs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_exports"),
        sa.UniqueConstraint("build_run_id", "name", name="uq_exports_build_name"),
    )


def downgrade() -> None:
    """Remove Phase 6 output metadata."""
    op.drop_table("exports")
    op.drop_table("build_lineage")
    op.drop_table("validation_results")
    op.drop_column("build_runs", "bundle_path")
    op.drop_column("build_runs", "dataset_checksum")
