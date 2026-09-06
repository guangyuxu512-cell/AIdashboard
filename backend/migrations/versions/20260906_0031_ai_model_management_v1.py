"""add AI model management V1 catalog

Revision ID: 20260906_0031
Revises: 20260905_0030
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260906_0031"
down_revision: str | None = "20260905_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GPT_IMAGE_2_MODEL_ID = "13b4f558-cd56-4f11-99fc-c64275e14031"


def upgrade() -> None:
    op.create_table(
        "ai_models",
        sa.Column("model_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("model_code", sa.String(length=100), nullable=False),
        sa.Column("provider_code", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "is_default",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("max_input_images", sa.Integer(), nullable=False),
        sa.Column(
            "supported_sizes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "supported_resolutions",
            postgresql.JSONB(astext_type=sa.Text()),
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
        sa.CheckConstraint(
            "length(trim(display_name)) > 0",
            name="display_name_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(model_code)) > 0",
            name="model_code_not_blank",
        ),
        sa.CheckConstraint("provider_code = 'toapis'", name="provider_code"),
        sa.CheckConstraint("NOT is_default OR enabled", name="default_enabled"),
        sa.CheckConstraint(
            "jsonb_typeof(capabilities) = 'array' "
            "AND jsonb_array_length(capabilities) > 0",
            name="capabilities_array",
        ),
        sa.CheckConstraint(
            "capabilities <@ '[\"NORMAL_GENERATION\", "
            "\"STYLE_REPLICATION\"]'::jsonb",
            name="capabilities_allowed",
        ),
        sa.CheckConstraint(
            "max_input_images >= 0",
            name="max_input_images_non_negative",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(supported_sizes) = 'array' "
            "AND jsonb_array_length(supported_sizes) > 0",
            name="supported_sizes_array",
        ),
        sa.CheckConstraint(
            "supported_sizes <@ '[\"1:1\", \"3:4\", \"4:3\", "
            "\"16:9\"]'::jsonb",
            name="supported_sizes_allowed",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(supported_resolutions) = 'array' "
            "AND jsonb_array_length(supported_resolutions) > 0",
            name="supported_resolutions_array",
        ),
        sa.CheckConstraint(
            "supported_resolutions <@ '[\"1k\", \"2k\", \"4k\"]'::jsonb",
            name="supported_resolutions_allowed",
        ),
        sa.PrimaryKeyConstraint("model_id", name="pk_ai_models"),
        sa.UniqueConstraint(
            "provider_code",
            "model_code",
            name="uq_ai_models_provider_model_code",
        ),
    )
    op.create_index(
        "uq_ai_models_enabled_default",
        "ai_models",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO ai_models (
                model_id,
                display_name,
                model_code,
                provider_code,
                enabled,
                is_default,
                capabilities,
                max_input_images,
                supported_sizes,
                supported_resolutions
            ) VALUES (
                CAST(:model_id AS uuid),
                'GPT Image 2',
                'gpt-image-2',
                'toapis',
                true,
                true,
                '["NORMAL_GENERATION", "STYLE_REPLICATION"]'::jsonb,
                6,
                '["1:1", "3:4", "4:3", "16:9"]'::jsonb,
                '["1k", "2k", "4k"]'::jsonb
            )
            """,
        ).bindparams(model_id=GPT_IMAGE_2_MODEL_ID),
    )


def downgrade() -> None:
    op.drop_index("uq_ai_models_enabled_default", table_name="ai_models")
    op.drop_table("ai_models")
