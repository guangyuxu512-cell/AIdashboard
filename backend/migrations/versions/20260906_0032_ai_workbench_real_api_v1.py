"""connect AI generation jobs to the model catalog

Revision ID: 20260906_0032
Revises: 20260906_0031
Create Date: 2026-09-06
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op


revision: str = "20260906_0032"
down_revision: str | None = "20260906_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _resolve_legacy_model_id() -> UUID:
    rows = list(
        op.get_bind()
        .execute(
            sa.text(
                """
                SELECT model_id
                FROM ai_models
                WHERE provider_code = 'toapis'
                  AND model_code = 'gpt-image-2'
                  AND enabled IS TRUE
                  AND is_default IS TRUE
                """,
            ),
        )
        .scalars()
    )
    if len(rows) != 1:
        raise RuntimeError(
            "AI generation model backfill requires the unique enabled default "
            "toapis/gpt-image-2 catalog model",
        )
    return rows[0]


def upgrade() -> None:
    op.add_column(
        "generation_jobs",
        sa.Column("model_id", sa.Uuid(), nullable=True),
    )
    model_id = _resolve_legacy_model_id()
    op.execute(
        sa.text(
            "UPDATE generation_jobs SET model_id = :model_id "
            "WHERE model_id IS NULL",
        ).bindparams(model_id=model_id),
    )
    op.alter_column(
        "generation_jobs",
        "model_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_generation_jobs_model_id_ai_models",
        "generation_jobs",
        "ai_models",
        ["model_id"],
        ["model_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_generation_jobs_model_id",
        "generation_jobs",
        ["model_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_generation_jobs_model_id", table_name="generation_jobs")
    op.drop_constraint(
        "fk_generation_jobs_model_id_ai_models",
        "generation_jobs",
        type_="foreignkey",
    )
    op.drop_column("generation_jobs", "model_id")
