"""Add build execution summaries and bounded previews.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store the bounded result needed by the Phase 5 preview workflow."""
    op.add_column("build_runs", sa.Column("row_count", sa.Integer(), nullable=True))
    op.add_column("build_runs", sa.Column("preview", sa.JSON(), nullable=True))
    op.add_column("build_runs", sa.Column("execution_summary", sa.JSON(), nullable=True))
    op.create_check_constraint(
        "build_row_count_nonnegative",
        "build_runs",
        "row_count IS NULL OR row_count >= 0",
    )


def downgrade() -> None:
    """Remove Phase 5 execution result fields."""
    op.drop_constraint("build_row_count_nonnegative", "build_runs", type_="check")
    op.drop_column("build_runs", "execution_summary")
    op.drop_column("build_runs", "preview")
    op.drop_column("build_runs", "row_count")
