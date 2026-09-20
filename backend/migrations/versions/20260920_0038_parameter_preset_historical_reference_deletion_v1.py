"""logically delete parameter presets while preserving historical references.

Revision ID: 20260920_0038
Revises: 20260919_0037
Create Date: 2026-09-20

Task rows own immutable input snapshots and archived Schedules cannot trigger
again.  The preset row must therefore remain available for those foreign-key
references while becoming unavailable for all new management and execution
paths.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260920_0038"
down_revision: str | None = "20260919_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "automation_parameter_presets",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_constraint(
        "uq_automation_preset_team_app_name",
        "automation_parameter_presets",
        type_="unique",
    )
    op.create_index(
        "uq_automation_preset_team_app_name",
        "automation_parameter_presets",
        ["team_id", "app_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    deleted_preset_count = int(
        op.get_bind().scalar(
            sa.text(
                "SELECT count(*) FROM automation_parameter_presets "
                "WHERE deleted_at IS NOT NULL",
            ),
        )
        or 0,
    )
    if deleted_preset_count:
        raise RuntimeError(
            "0038降级前置条件未满足：存在"
            f"{deleted_preset_count}条已逻辑删除的参数预设，"
            "不能安全恢复物理删除和全量名称唯一约束",
        )

    op.drop_index(
        "uq_automation_preset_team_app_name",
        table_name="automation_parameter_presets",
    )
    op.create_unique_constraint(
        "uq_automation_preset_team_app_name",
        "automation_parameter_presets",
        ["team_id", "app_id", "name"],
    )
    op.drop_column("automation_parameter_presets", "deleted_at")
