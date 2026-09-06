"""add AI Workbench management data foundation

Revision ID: 20260903_0026
Revises: 20260902_0025
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260903_0026"
down_revision: str | None = "20260902_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "template_groups",
        sa.Column("template_group_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
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
        sa.CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        sa.CheckConstraint(
            "mode IN ('NORMAL_GENERATION', 'STYLE_REPLICATION')",
            name="mode",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.team_id"],
            name="fk_template_groups_team_id_teams",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.user_id"],
            name="fk_template_groups_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "template_group_id",
            name="pk_template_groups",
        ),
    )
    op.create_index(
        "ix_template_groups_created_group",
        "template_groups",
        ["created_at", "template_group_id"],
        unique=False,
    )
    op.create_index(
        "ix_template_groups_team_created_group",
        "template_groups",
        ["team_id", "created_at", "template_group_id"],
        unique=False,
    )
    op.create_index(
        "ix_template_groups_team_creator_created_group",
        "template_groups",
        ["team_id", "created_by_user_id", "created_at", "template_group_id"],
        unique=False,
    )

    op.create_table(
        "product_material_groups",
        sa.Column("material_group_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "normal_generation_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "style_replication_enabled",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
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
        sa.CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.team_id"],
            name="fk_product_material_groups_team_id_teams",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.user_id"],
            name="fk_product_material_groups_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "material_group_id",
            name="pk_product_material_groups",
        ),
    )
    op.create_index(
        "ix_product_material_groups_created_group",
        "product_material_groups",
        ["created_at", "material_group_id"],
        unique=False,
    )
    op.create_index(
        "ix_product_material_groups_team_created_group",
        "product_material_groups",
        ["team_id", "created_at", "material_group_id"],
        unique=False,
    )
    op.create_index(
        "ix_product_material_groups_team_creator_created_group",
        "product_material_groups",
        ["team_id", "created_by_user_id", "created_at", "material_group_id"],
        unique=False,
    )

    op.create_table(
        "prompt_templates",
        sa.Column("prompt_template_id", sa.Uuid(), nullable=False),
        sa.Column("template_group_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("output_role", sa.String(length=16), nullable=False),
        sa.Column("output_format", sa.String(length=16), nullable=False),
        sa.Column("size", sa.String(length=5), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column(
            "variables",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
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
        sa.CheckConstraint("count BETWEEN 1 AND 8", name="count"),
        sa.CheckConstraint(
            "jsonb_typeof(variables) = 'array'",
            name="variables_array",
        ),
        sa.CheckConstraint("length(trim(prompt)) > 0", name="prompt_not_blank"),
        sa.CheckConstraint("sort_order > 0", name="sort_order_positive"),
        sa.ForeignKeyConstraint(
            ["template_group_id"],
            ["template_groups.template_group_id"],
            name="fk_prompt_templates_template_group_id_template_groups",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "prompt_template_id",
            name="pk_prompt_templates",
        ),
        sa.UniqueConstraint(
            "template_group_id",
            "sort_order",
            name="uq_prompt_templates_group_sort_order",
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    op.create_table(
        "material_group_assets",
        sa.Column("material_group_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('PRODUCT_SOURCE', 'STYLE_REFERENCE', 'AI_OUTPUT')",
            name="role",
        ),
        sa.ForeignKeyConstraint(
            ["material_group_id"],
            ["product_material_groups.material_group_id"],
            name="fk_material_group_assets_material_group",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.asset_id"],
            name="fk_material_group_assets_asset",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "material_group_id",
            "asset_id",
            name="pk_material_group_assets",
        ),
    )
    op.create_index(
        "ix_material_group_assets_asset_group",
        "material_group_assets",
        ["asset_id", "material_group_id"],
        unique=False,
    )

    op.create_table(
        "material_group_template_bindings",
        sa.Column("material_group_id", sa.Uuid(), nullable=False),
        sa.Column("template_group_id", sa.Uuid(), nullable=False),
        sa.Column("generation_mode", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "generation_mode IN ('NORMAL_GENERATION', 'STYLE_REPLICATION')",
            name="generation_mode",
        ),
        sa.CheckConstraint("position >= 0", name="position_non_negative"),
        sa.ForeignKeyConstraint(
            ["material_group_id"],
            ["product_material_groups.material_group_id"],
            name="fk_material_template_bindings_material_group",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["template_group_id"],
            ["template_groups.template_group_id"],
            name="fk_material_template_bindings_template_group",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "material_group_id",
            "template_group_id",
            name="pk_material_group_template_bindings",
        ),
        sa.UniqueConstraint(
            "material_group_id",
            "generation_mode",
            "position",
            name="uq_material_group_template_bindings_group_mode_position",
        ),
    )
    op.create_index(
        "ix_material_group_template_bindings_template_group",
        "material_group_template_bindings",
        ["template_group_id", "material_group_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_material_group_template_bindings_template_group",
        table_name="material_group_template_bindings",
    )
    op.drop_table("material_group_template_bindings")
    op.drop_index(
        "ix_material_group_assets_asset_group",
        table_name="material_group_assets",
    )
    op.drop_table("material_group_assets")
    op.drop_table("prompt_templates")
    op.drop_index(
        "ix_product_material_groups_team_creator_created_group",
        table_name="product_material_groups",
    )
    op.drop_index(
        "ix_product_material_groups_team_created_group",
        table_name="product_material_groups",
    )
    op.drop_index(
        "ix_product_material_groups_created_group",
        table_name="product_material_groups",
    )
    op.drop_table("product_material_groups")
    op.drop_index(
        "ix_template_groups_team_creator_created_group",
        table_name="template_groups",
    )
    op.drop_index(
        "ix_template_groups_team_created_group",
        table_name="template_groups",
    )
    op.drop_index(
        "ix_template_groups_created_group",
        table_name="template_groups",
    )
    op.drop_table("template_groups")
