"""Add versioned recipes and deterministic build planning.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create recipe, immutable version, variable, transformation, and build-plan tables."""
    op.create_table(
        "dataset_recipes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("draft_content", sa.JSON(), nullable=False),
        sa.Column("draft_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("length(name) > 0", name="recipe_name_not_empty"),
        sa.CheckConstraint("length(draft_hash) = 64", name="recipe_draft_hash_length"),
        sa.PrimaryKeyConstraint("id", name="pk_dataset_recipes"),
    )
    op.create_table(
        "recipe_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("version_number > 0", name="recipe_version_positive"),
        sa.CheckConstraint("length(content_hash) = 64", name="recipe_content_hash_length"),
        sa.ForeignKeyConstraint(
            ["recipe_id"],
            ["dataset_recipes.id"],
            name="fk_recipe_versions_recipe_id_dataset_recipes",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_recipe_versions"),
        sa.UniqueConstraint("recipe_id", "content_hash", name="uq_recipe_versions_content"),
        sa.UniqueConstraint("recipe_id", "version_number", name="uq_recipe_versions_number"),
    )
    op.create_table(
        "recipe_variables",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipe_version_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("indicator_id", sa.String(length=128), nullable=False),
        sa.Column("output_name", sa.String(length=128), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.CheckConstraint("position >= 0", name="recipe_variable_position_nonnegative"),
        sa.ForeignKeyConstraint(
            ["recipe_version_id"],
            ["recipe_versions.id"],
            name="fk_recipe_variables_recipe_version_id_recipe_versions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_recipe_variables"),
        sa.UniqueConstraint(
            "recipe_version_id", "output_name", name="uq_recipe_variables_output_name"
        ),
        sa.UniqueConstraint("recipe_version_id", "position", name="uq_recipe_variables_position"),
    )
    op.create_table(
        "transformation_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipe_version_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.CheckConstraint("position >= 0", name="transformation_position_nonnegative"),
        sa.ForeignKeyConstraint(
            ["recipe_version_id"],
            ["recipe_versions.id"],
            name="fk_transformation_steps_recipe_version_id_recipe_versions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transformation_steps"),
        sa.UniqueConstraint(
            "recipe_version_id", "position", name="uq_transformation_steps_position"
        ),
    )
    op.create_table(
        "build_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipe_version_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "planned",
                "retrieving",
                "transforming",
                "validating",
                "exporting",
                "succeeded",
                "failed",
                name="build_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("build_identity", sa.String(length=64), nullable=False),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.CheckConstraint("length(build_identity) = 64", name="build_identity_length"),
        sa.ForeignKeyConstraint(
            ["recipe_version_id"],
            ["recipe_versions.id"],
            name="fk_build_runs_recipe_version_id_recipe_versions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_build_runs"),
        sa.UniqueConstraint("build_identity", name="uq_build_runs_identity"),
    )
    op.create_table(
        "build_inputs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("build_run_id", sa.Uuid(), nullable=False),
        sa.Column("output_name", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("indicator_id", sa.String(length=128), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("indicator_metadata", sa.JSON(), nullable=False),
        sa.Column("indicator_fingerprint", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "length(indicator_fingerprint) = 64", name="build_input_fingerprint_length"
        ),
        sa.ForeignKeyConstraint(
            ["build_run_id"],
            ["build_runs.id"],
            name="fk_build_inputs_build_run_id_build_runs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_build_inputs"),
        sa.UniqueConstraint("build_run_id", "output_name", name="uq_build_inputs_output_name"),
    )


def downgrade() -> None:
    """Remove Phase 4 build-planning tables in dependency order."""
    op.drop_table("build_inputs")
    op.drop_table("build_runs")
    op.drop_table("transformation_steps")
    op.drop_table("recipe_variables")
    op.drop_table("recipe_versions")
    op.drop_table("dataset_recipes")
