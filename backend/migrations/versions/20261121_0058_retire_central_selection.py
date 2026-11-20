"""Retire old central selection after its replacement is operational.

Revision ID: 20261121_0058
Revises: 20261120_0057

The user authorized discarding the retired selection facts and schedules. A
verified backup is required before applying this migration to a shared database.
Worker tasks, generic schedules and Operations Center schedules are retained.
"""
from alembic import op
import sqlalchemy as sa


revision = "20261121_0058"
down_revision = "20261120_0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError("0058 requires online verification of old selection activity")
    connection = op.get_bind()
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("LOCK TABLE schedules, schedule_runs, product_selection_runs IN ACCESS EXCLUSIVE MODE")
    if connection.scalar(sa.text(
        "SELECT EXISTS (SELECT 1 FROM product_selection_runs "
        "WHERE status = 'running' AND (lease_expires_at IS NULL OR lease_expires_at > now()))"
    )):
        raise RuntimeError("A central selection run still has an active lease")

    op.execute("DELETE FROM membership_module_accesses WHERE module_code = 'product-selection'")
    op.execute("DELETE FROM team_module_accesses WHERE module_code = 'product-selection'")
    op.execute("""
        UPDATE api_tokens AS token
        SET permissions = COALESCE(
            (SELECT json_agg(item.value ORDER BY item.ordinality)
             FROM json_array_elements_text(token.permissions) WITH ORDINALITY AS item(value, ordinality)
             WHERE item.value NOT LIKE '% /api/v1/product-selection/%'),
            '[]'::json
        )
        WHERE EXISTS (
            SELECT 1 FROM json_array_elements_text(token.permissions) AS item(value)
            WHERE item.value LIKE '% /api/v1/product-selection/%'
        )
    """)

    op.execute("DELETE FROM historical_schedule_shop_refs WHERE schedule_id IN "
               "(SELECT schedule_id FROM schedules WHERE target_kind = 'server_selection')")
    op.execute("DELETE FROM schedule_runs WHERE schedule_id IN "
               "(SELECT schedule_id FROM schedules WHERE target_kind = 'server_selection')")
    op.execute("DELETE FROM schedules WHERE target_kind = 'server_selection'")

    for name in ("target_result", "trigger_result"):
        op.drop_constraint(op.f(f"ck_schedule_runs_{name}"), "schedule_runs", type_="check")
    op.drop_constraint("fk_schedule_runs_selection_run", "schedule_runs", type_="foreignkey")
    op.drop_column("schedule_runs", "selection_run_id")
    op.create_check_constraint(op.f("ck_schedule_runs_trigger_result"), "schedule_runs",
                               "trigger_result IN ('task_created', 'blocked')")
    op.create_check_constraint(op.f("ck_schedule_runs_target_result"), "schedule_runs",
                               "(trigger_result = 'task_created' AND task_id IS NOT NULL) OR "
                               "(trigger_result = 'blocked' AND task_id IS NULL)")

    for name in ("target_fields", "target_kind", "time_fields", "rule_fields", "schedule_type"):
        op.drop_constraint(op.f(f"ck_schedules_{name}"), "schedules", type_="check")
    op.drop_index("uq_schedules_selection_strategy", table_name="schedules")
    op.drop_constraint("fk_schedules_selection_strategy", "schedules", type_="foreignkey")
    op.drop_column("schedules", "selection_strategy_id")
    op.drop_column("schedules", "interval_hours")
    op.create_check_constraint(op.f("ck_schedules_schedule_type"), "schedules",
                               "schedule_type IN ('once', 'daily', 'weekly')")
    op.create_check_constraint(op.f("ck_schedules_rule_fields"), "schedules",
                               "(schedule_type = 'once' AND local_date IS NOT NULL AND jsonb_array_length(weekdays) = 0) OR "
                               "(schedule_type = 'daily' AND local_date IS NULL AND jsonb_array_length(weekdays) = 0) OR "
                               "(schedule_type = 'weekly' AND local_date IS NULL AND jsonb_array_length(weekdays) > 0)")
    op.create_check_constraint(op.f("ck_schedules_target_kind"), "schedules", "target_kind = 'pc'")
    op.create_check_constraint(op.f("ck_schedules_target_fields"), "schedules",
                               "target_device_id IS NOT NULL AND skill_id IS NOT NULL")
    op.create_check_constraint(op.f("ck_schedules_time_fields"), "schedules", "local_time IS NOT NULL")

    op.drop_constraint("fk_selection_run_basic_observation", "product_selection_runs", type_="foreignkey")
    for table in ("product_selection_result_items", "product_selection_observations", "product_selection_runs",
                  "product_selection_strategies", "product_selection_candidates"):
        op.drop_table(table)


def downgrade() -> None:
    raise RuntimeError("0058 removed central selection history; restore a verified backup to recover it")
