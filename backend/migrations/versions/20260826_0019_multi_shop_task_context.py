"""add ordered multi-shop task and schedule context

Revision ID: 20260826_0019
Revises: 20260825_0018
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260826_0019"
down_revision: str | None = "20260825_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_shops",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position >= 0", name="position_non_negative"),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shops.shop_id"],
            name="fk_task_shops_shop_id_shops",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name="fk_task_shops_task_id_tasks",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("task_id", "shop_id", name="pk_task_shops"),
        sa.UniqueConstraint(
            "task_id",
            "position",
            name="uq_task_shops_task_position",
        ),
    )
    op.create_index(
        "ix_task_shops_shop_task",
        "task_shops",
        ["shop_id", "task_id"],
        unique=False,
    )
    op.create_table(
        "schedule_shops",
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position >= 0", name="position_non_negative"),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["schedules.schedule_id"],
            name="fk_schedule_shops_schedule_id_schedules",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shops.shop_id"],
            name="fk_schedule_shops_shop_id_shops",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "schedule_id",
            "shop_id",
            name="pk_schedule_shops",
        ),
        sa.UniqueConstraint(
            "schedule_id",
            "position",
            name="uq_schedule_shops_schedule_position",
        ),
    )
    op.create_index(
        "ix_schedule_shops_shop_schedule",
        "schedule_shops",
        ["shop_id", "schedule_id"],
        unique=False,
    )

    op.execute(
        "INSERT INTO task_shops (task_id, shop_id, position) "
        "SELECT task_id, shop_id, 0 FROM tasks WHERE shop_id IS NOT NULL",
    )
    op.execute(
        "INSERT INTO schedule_shops (schedule_id, shop_id, position) "
        "SELECT schedule_id, shop_id, 0 FROM schedules WHERE shop_id IS NOT NULL",
    )

    op.drop_constraint("fk_tasks_shop_id_shops", "tasks", type_="foreignkey")
    op.drop_column("tasks", "shop_id")
    op.drop_constraint(
        "fk_schedules_shop_id_shops",
        "schedules",
        type_="foreignkey",
    )
    op.drop_column("schedules", "shop_id")

    op.drop_index(
        "uq_shop_device_bindings_enabled_primary",
        table_name="shop_device_bindings",
    )
    op.drop_constraint(
        op.f("ck_shop_device_bindings_binding_role"),
        "shop_device_bindings",
        type_="check",
    )
    op.drop_column("shop_device_bindings", "binding_role")


def downgrade() -> None:
    op.add_column(
        "shop_device_bindings",
        sa.Column("binding_role", sa.String(length=7), nullable=True),
    )
    op.execute(
        "WITH ranked AS ("
        " SELECT shop_id, device_id,"
        " row_number() OVER ("
        " PARTITION BY shop_id ORDER BY enabled DESC, created_at, device_id"
        " ) AS position"
        " FROM shop_device_bindings"
        ") UPDATE shop_device_bindings AS binding"
        " SET binding_role = CASE WHEN ranked.position = 1"
        " THEN 'primary' ELSE 'backup' END"
        " FROM ranked WHERE binding.shop_id = ranked.shop_id"
        " AND binding.device_id = ranked.device_id",
    )
    op.alter_column(
        "shop_device_bindings",
        "binding_role",
        existing_type=sa.String(length=7),
        nullable=False,
    )
    op.create_check_constraint(
        op.f("ck_shop_device_bindings_binding_role"),
        "shop_device_bindings",
        "binding_role IN ('primary', 'backup')",
    )
    op.create_index(
        "uq_shop_device_bindings_enabled_primary",
        "shop_device_bindings",
        ["shop_id"],
        unique=True,
        postgresql_where=sa.text("enabled AND binding_role = 'primary'"),
    )

    op.add_column("tasks", sa.Column("shop_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_shop_id_shops",
        "tasks",
        "shops",
        ["shop_id"],
        ["shop_id"],
        ondelete="RESTRICT",
    )
    op.execute(
        "UPDATE tasks SET shop_id = task_shops.shop_id"
        " FROM task_shops WHERE task_shops.task_id = tasks.task_id"
        " AND task_shops.position = 0",
    )
    op.add_column("schedules", sa.Column("shop_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_schedules_shop_id_shops",
        "schedules",
        "shops",
        ["shop_id"],
        ["shop_id"],
        ondelete="RESTRICT",
    )
    op.execute(
        "UPDATE schedules SET shop_id = schedule_shops.shop_id"
        " FROM schedule_shops"
        " WHERE schedule_shops.schedule_id = schedules.schedule_id"
        " AND schedule_shops.position = 0",
    )

    op.drop_index(
        "ix_schedule_shops_shop_schedule",
        table_name="schedule_shops",
    )
    op.drop_table("schedule_shops")
    op.drop_index("ix_task_shops_shop_task", table_name="task_shops")
    op.drop_table("task_shops")
