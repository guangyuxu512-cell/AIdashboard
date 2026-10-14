"""Reuse Schedule/Run for server selection and bounded shared execution slots."""

from alembic import op
import sqlalchemy as sa

revision = "20261013_0045"
down_revision = "20261013_0044"
branch_labels = None
depends_on = None

RULE_FIELDS = (
    "(schedule_type = 'once' AND local_date IS NOT NULL AND jsonb_array_length(weekdays) = 0) OR "
    "(schedule_type = 'daily' AND local_date IS NULL AND jsonb_array_length(weekdays) = 0) OR "
    "(schedule_type = 'weekly' AND local_date IS NULL AND jsonb_array_length(weekdays) > 0)"
)
TARGET_FIELDS = (
    "(target_kind = 'pc' AND target_device_id IS NOT NULL AND skill_id IS NOT NULL "
    "AND selection_strategy_id IS NULL AND schedule_type IN ('once', 'daily', 'weekly')) OR "
    "(target_kind = 'server_selection' AND selection_strategy_id IS NOT NULL "
    "AND target_device_id IS NULL AND skill_id IS NULL AND parameter_preset_id IS NULL "
    "AND task_input_json = '{}'::jsonb AND timezone = 'Asia/Shanghai' AND schedule_type IN ('hourly', 'daily'))"
)
TIME_FIELDS = (
    "(target_kind = 'server_selection' AND schedule_type = 'hourly' AND local_time IS NULL "
    "AND interval_hours IS NOT NULL AND interval_hours > 0) OR "
    "(schedule_type <> 'hourly' AND local_time IS NOT NULL AND interval_hours IS NULL)"
)
TARGET_RESULT = (
    "(trigger_result = 'task_created' AND task_id IS NOT NULL AND selection_run_id IS NULL) OR "
    "(trigger_result = 'blocked' AND task_id IS NULL AND selection_run_id IS NULL) OR "
    "(trigger_result = 'selection_run' AND task_id IS NULL AND selection_run_id IS NOT NULL)"
)


def _legacy_check(connection, table: str, logical: str) -> str:
    # Earlier applied migrations passed fully prefixed names through the
    # naming convention. Verify the live known spelling instead of rewriting
    # them or guessing which arbitrary constraint to remove.
    known = {f"ck_{table}_{logical}", f"ck_{table}_ck_{table}_{logical}"}
    found = [row["name"] for row in sa.inspect(connection).get_check_constraints(table) if row["name"] in known]
    if len(found) != 1:
        raise RuntimeError("Existing schedule constraint identity requires review")
    return found[0]


def upgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError("0045 upgrade requires online compatibility verification")
    connection = op.get_bind()
    connection.execute(sa.text("LOCK TABLE schedules, schedule_runs, product_selection_runs IN ACCESS EXCLUSIVE MODE"))
    if connection.scalar(sa.text(
        "SELECT EXISTS(SELECT 1 FROM schedules WHERE target_device_id IS NULL OR skill_id IS NULL OR local_time IS NULL) "
        "OR EXISTS(SELECT 1 FROM schedule_runs WHERE NOT ((trigger_result = 'task_created' AND task_id IS NOT NULL) "
        "OR (trigger_result = 'blocked' AND task_id IS NULL)))"
    )):
        raise RuntimeError("Existing PC schedule facts are incompatible; retain and review them before upgrading")
    schedule_type_check = _legacy_check(connection, "schedules", "schedule_type")
    rule_check = _legacy_check(connection, "schedules", "rule_fields")
    trigger_check = _legacy_check(connection, "schedule_runs", "trigger_result")
    op.add_column("schedules", sa.Column("target_kind", sa.String(24), server_default="pc", nullable=False))
    op.add_column("schedules", sa.Column("selection_strategy_id", sa.Uuid(), nullable=True))
    op.add_column("schedules", sa.Column("interval_hours", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_schedules_selection_strategy", "schedules", "product_selection_strategies", ["selection_strategy_id"], ["strategy_id"], ondelete="RESTRICT")
    op.alter_column("schedules", "target_device_id", existing_type=sa.Uuid(), nullable=True)
    op.alter_column("schedules", "skill_id", existing_type=sa.String(200), nullable=True)
    op.alter_column("schedules", "local_time", existing_type=sa.Time(), nullable=True)
    op.drop_constraint(op.f(schedule_type_check), "schedules", type_="check")
    op.drop_constraint(op.f(rule_check), "schedules", type_="check")
    op.create_check_constraint(op.f("ck_schedules_schedule_type"), "schedules", "schedule_type IN ('once','daily','weekly','hourly')")
    op.create_check_constraint(op.f("ck_schedules_rule_fields"), "schedules", RULE_FIELDS + " OR (schedule_type = 'hourly' AND local_date IS NULL AND jsonb_array_length(weekdays) = 0)")
    op.create_check_constraint(op.f("ck_schedules_target_kind"), "schedules", "target_kind IN ('pc','server_selection')")
    op.create_check_constraint(op.f("ck_schedules_target_fields"), "schedules", TARGET_FIELDS)
    op.create_check_constraint(op.f("ck_schedules_time_fields"), "schedules", TIME_FIELDS)
    op.create_index("uq_schedules_selection_strategy", "schedules", ["selection_strategy_id"], unique=True, postgresql_where=sa.text("target_kind = 'server_selection' AND deleted_at IS NULL"))
    op.add_column("schedule_runs", sa.Column("selection_run_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_schedule_runs_selection_run", "schedule_runs", "product_selection_runs", ["selection_run_id"], ["run_id"], ondelete="RESTRICT")
    op.drop_constraint(op.f(trigger_check), "schedule_runs", type_="check")
    op.create_check_constraint(op.f("ck_schedule_runs_trigger_result"), "schedule_runs", "trigger_result IN ('task_created','blocked','selection_run')")
    op.create_check_constraint(op.f("ck_schedule_runs_target_result"), "schedule_runs", TARGET_RESULT)
    op.drop_index("uq_selection_run_running", table_name="product_selection_runs")
    op.create_index("uq_selection_run_running_shop", "product_selection_runs", ["request_shop_id"], unique=True, postgresql_where=sa.text("status = 'running'"))
    op.create_index("uq_selection_run_running_strategy", "product_selection_runs", ["strategy_id"], unique=True, postgresql_where=sa.text("status = 'running' AND strategy_id IS NOT NULL"))


def downgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError("0045 downgrade requires online verification of the registered Feature database")
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT current_database()")) != "control_center_feat_product_selection":
        raise RuntimeError("0045 downgrade only permits the registered rebuildable Product Selection Feature database")
    connection.execute(sa.text("LOCK TABLE schedules, schedule_runs, product_selection_runs IN ACCESS EXCLUSIVE MODE"))
    if connection.scalar(sa.text(
        "SELECT EXISTS(SELECT 1 FROM schedules WHERE target_kind <> 'pc' OR schedule_type = 'hourly' "
        "OR selection_strategy_id IS NOT NULL OR interval_hours IS NOT NULL OR target_device_id IS NULL OR skill_id IS NULL OR local_time IS NULL) "
        "OR EXISTS(SELECT 1 FROM schedule_runs WHERE selection_run_id IS NOT NULL OR trigger_result = 'selection_run') "
        "OR (SELECT count(*) FROM product_selection_runs WHERE status = 'running') > 1 "
        "OR EXISTS(SELECT 1 FROM product_selection_runs WHERE request_conditions->'strategy_queue' IS NOT NULL "
        "AND request_conditions->'strategy_queue' <> 'null'::jsonb)"
    )):
        raise RuntimeError("Server selection history or queue facts exist; retain schema and use a compatible application rollback")
    op.drop_index("uq_selection_run_running_strategy", table_name="product_selection_runs")
    op.drop_index("uq_selection_run_running_shop", table_name="product_selection_runs")
    op.create_index("uq_selection_run_running", "product_selection_runs", [sa.text("(1)")], unique=True, postgresql_where=sa.text("status = 'running'"))
    op.drop_constraint(op.f("ck_schedule_runs_target_result"), "schedule_runs", type_="check")
    op.drop_constraint(op.f("ck_schedule_runs_trigger_result"), "schedule_runs", type_="check")
    op.create_check_constraint(op.f("ck_schedule_runs_ck_schedule_runs_trigger_result"), "schedule_runs", "trigger_result IN ('task_created','blocked')")
    op.drop_constraint("fk_schedule_runs_selection_run", "schedule_runs", type_="foreignkey")
    op.drop_column("schedule_runs", "selection_run_id")
    op.drop_index("uq_schedules_selection_strategy", table_name="schedules")
    for name in ("target_kind", "target_fields", "time_fields", "schedule_type", "rule_fields"):
        op.drop_constraint(op.f("ck_schedules_" + name), "schedules", type_="check")
    op.create_check_constraint(op.f("ck_schedules_ck_schedules_schedule_type"), "schedules", "schedule_type IN ('once','daily','weekly')")
    op.create_check_constraint(op.f("ck_schedules_ck_schedules_rule_fields"), "schedules", RULE_FIELDS)
    op.alter_column("schedules", "local_time", existing_type=sa.Time(), nullable=False)
    op.alter_column("schedules", "skill_id", existing_type=sa.String(200), nullable=False)
    op.alter_column("schedules", "target_device_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_constraint("fk_schedules_selection_strategy", "schedules", type_="foreignkey")
    for name in ("interval_hours", "selection_strategy_id", "target_kind"):
        op.drop_column("schedules", name)
