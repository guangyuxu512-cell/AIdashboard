"""add AI generation execution V1

Revision ID: 20260903_0027
Revises: 20260903_0026
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260903_0027"
down_revision: str | None = "20260903_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generation_jobs",
        sa.Column("generation_job_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_display_name", sa.String(length=100), nullable=False),
        sa.Column("work_mode", sa.String(length=16), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column("submission_key", sa.String(length=128), nullable=False),
        sa.Column("submission_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "work_mode IN ('INSTANT', 'BATCH')",
            name="work_mode",
        ),
        sa.CheckConstraint(
            "mode IN ('NORMAL_GENERATION', 'STYLE_REPLICATION')",
            name="mode",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCESS', "
            "'PARTIAL_FAILED', 'FAILED')",
            name="status",
        ),
        sa.CheckConstraint(
            "length(trim(created_by_display_name)) > 0",
            name="creator_name_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(submission_key)) > 0",
            name="submission_key_not_blank",
        ),
        sa.CheckConstraint(
            "length(submission_fingerprint) = 64",
            name="submission_fingerprint_length",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.team_id"],
            name="fk_generation_jobs_team_id_teams",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.user_id"],
            name="fk_generation_jobs_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("generation_job_id", name="pk_generation_jobs"),
        sa.UniqueConstraint(
            "team_id",
            "created_by_user_id",
            "submission_key",
            name="uq_generation_jobs_owner_submission_key",
        ),
    )
    op.create_index(
        "ix_generation_jobs_created_job",
        "generation_jobs",
        ["created_at", "generation_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_generation_jobs_team_created_job",
        "generation_jobs",
        ["team_id", "created_at", "generation_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_generation_jobs_team_creator_created_job",
        "generation_jobs",
        ["team_id", "created_by_user_id", "created_at", "generation_job_id"],
        unique=False,
    )

    op.create_table(
        "generation_items",
        sa.Column("generation_item_id", sa.Uuid(), nullable=False),
        sa.Column("generation_job_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column("final_prompt", sa.Text(), nullable=False),
        sa.Column("output_role", sa.String(length=16), nullable=False),
        sa.Column("output_format", sa.String(length=16), nullable=False),
        sa.Column("size", sa.String(length=5), nullable=False),
        sa.Column("source_product_position", sa.Integer(), nullable=True),
        sa.Column("source_template_group_position", sa.Integer(), nullable=True),
        sa.Column("source_prompt_template_position", sa.Integer(), nullable=True),
        sa.Column("output_ordinal", sa.Integer(), nullable=False),
        sa.Column("source_product_material_group_id", sa.Uuid(), nullable=True),
        sa.Column("source_template_group_id", sa.Uuid(), nullable=True),
        sa.Column("source_prompt_template_id", sa.Uuid(), nullable=True),
        sa.Column("product_name_snapshot", sa.String(length=100), nullable=True),
        sa.Column(
            "template_group_name_snapshot",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "prompt_template_name_snapshot",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column("output_asset_id", sa.Uuid(), nullable=True),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("last_failure_code", sa.String(length=64), nullable=True),
        sa.Column("last_failure_message", sa.Text(), nullable=True),
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_material_group_id", sa.Uuid(), nullable=True),
        sa.Column(
            "archived_material_group_name_snapshot",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("position >= 0", name="position_non_negative"),
        sa.CheckConstraint(
            "source_product_position IS NULL OR source_product_position >= 0",
            name="source_product_position_non_negative",
        ),
        sa.CheckConstraint(
            "source_template_group_position IS NULL OR "
            "source_template_group_position >= 0",
            name="source_template_group_position_non_negative",
        ),
        sa.CheckConstraint(
            "source_prompt_template_position IS NULL OR "
            "source_prompt_template_position >= 0",
            name="source_prompt_position_non_negative",
        ),
        sa.CheckConstraint("output_ordinal >= 0", name="output_ordinal_non_negative"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCESS', 'FAILED')",
            name="status",
        ),
        sa.CheckConstraint(
            "length(trim(final_prompt)) > 0",
            name="final_prompt_not_blank",
        ),
        sa.CheckConstraint(
            "output_role IN ('MAIN_IMAGE', 'DETAIL_IMAGE')",
            name="output_role",
        ),
        sa.CheckConstraint(
            "output_format IN ('SINGLE', 'COLLAGE_2X2')",
            name="output_format",
        ),
        sa.CheckConstraint(
            "size IN ('1:1', '3:4', '4:3', '16:9')",
            name="size",
        ),
        sa.CheckConstraint("attempt_count > 0", name="attempt_count_positive"),
        sa.CheckConstraint(
            "status <> 'SUCCESS' OR output_asset_id IS NOT NULL",
            name="success_has_output_asset",
        ),
        sa.ForeignKeyConstraint(
            ["generation_job_id"],
            ["generation_jobs.generation_job_id"],
            name="fk_generation_items_generation_job",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_product_material_group_id"],
            ["product_material_groups.material_group_id"],
            name="fk_generation_items_source_material_group",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_template_group_id"],
            ["template_groups.template_group_id"],
            name="fk_generation_items_source_template_group",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_prompt_template_id"],
            ["prompt_templates.prompt_template_id"],
            name="fk_generation_items_source_prompt_template",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["output_asset_id"],
            ["assets.asset_id"],
            name="fk_generation_items_output_asset",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["archived_material_group_id"],
            ["product_material_groups.material_group_id"],
            name="fk_generation_items_archived_material_group",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("generation_item_id", name="pk_generation_items"),
        sa.UniqueConstraint(
            "generation_job_id",
            "position",
            name="uq_generation_items_job_position",
        ),
        sa.UniqueConstraint(
            "output_asset_id",
            name="uq_generation_items_output_asset",
        ),
    )
    op.create_index(
        "ix_generation_items_job_status_position",
        "generation_items",
        ["generation_job_id", "status", "position"],
        unique=False,
    )
    op.create_index(
        "ix_generation_items_source_material_job",
        "generation_items",
        ["source_product_material_group_id", "generation_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_generation_items_source_template_group",
        "generation_items",
        ["source_template_group_id"],
        unique=False,
    )
    op.create_index(
        "ix_generation_items_source_prompt_template",
        "generation_items",
        ["source_prompt_template_id"],
        unique=False,
    )
    op.create_index(
        "ix_generation_items_archived_material_group",
        "generation_items",
        ["archived_material_group_id"],
        unique=False,
    )

    op.create_table(
        "generation_item_assets",
        sa.Column("generation_item_id", sa.Uuid(), nullable=False),
        sa.Column("input_role", sa.String(length=20), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "input_role IN ('PRODUCT_SOURCE', 'STYLE_REFERENCE')",
            name="input_role",
        ),
        sa.CheckConstraint("position >= 0", name="position_non_negative"),
        sa.ForeignKeyConstraint(
            ["generation_item_id"],
            ["generation_items.generation_item_id"],
            name="fk_generation_item_assets_generation_item",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.asset_id"],
            name="fk_generation_item_assets_asset",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "generation_item_id",
            "input_role",
            "position",
            name="pk_generation_item_assets",
        ),
        sa.UniqueConstraint(
            "generation_item_id",
            "input_role",
            "asset_id",
            name="uq_generation_item_assets_item_role_asset",
        ),
    )
    op.create_index(
        "ix_generation_item_assets_asset_item",
        "generation_item_assets",
        ["asset_id", "generation_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_generation_item_assets_asset_item",
        table_name="generation_item_assets",
    )
    op.drop_table("generation_item_assets")
    op.drop_index(
        "ix_generation_items_archived_material_group",
        table_name="generation_items",
    )
    op.drop_index(
        "ix_generation_items_source_prompt_template",
        table_name="generation_items",
    )
    op.drop_index(
        "ix_generation_items_source_template_group",
        table_name="generation_items",
    )
    op.drop_index(
        "ix_generation_items_source_material_job",
        table_name="generation_items",
    )
    op.drop_index(
        "ix_generation_items_job_status_position",
        table_name="generation_items",
    )
    op.drop_table("generation_items")
    op.drop_index(
        "ix_generation_jobs_team_creator_created_job",
        table_name="generation_jobs",
    )
    op.drop_index(
        "ix_generation_jobs_team_created_job",
        table_name="generation_jobs",
    )
    op.drop_index(
        "ix_generation_jobs_created_job",
        table_name="generation_jobs",
    )
    op.drop_table("generation_jobs")
