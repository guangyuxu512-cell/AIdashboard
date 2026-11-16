"""Retire central shop credentials, bindings and legacy execution.

Revision ID: 20261116_0056
Revises: 20261116_0055

Historical business facts and their identity/permission references remain read
only.  A verified backup is required before applying this irreversible change.
"""
from alembic import op


revision = "20261116_0056"
down_revision = "20261116_0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    # Never declare a running legacy task stopped while an old worker could be
    # executing it.  The operator must quiesce it before running the upgrade.
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM tasks t
            WHERE t.status = 'running' AND (
              t.skill_id LIKE 'yingdao.%' OR
              EXISTS (SELECT 1 FROM task_shops ts WHERE ts.task_id = t.task_id)
            )
          ) THEN
            RAISE EXCEPTION 'active legacy tasks must finish before upgrade';
          END IF;
        END $$
    """)
    op.execute("""
        UPDATE tasks t
           SET status = 'failed', error_code = 'LEGACY_TASK_RETIRED',
               error_message = '旧执行方式已停用', finished_at = now(),
               lease_until = NULL, updated_at = now()
         WHERE t.status = 'pending' AND (
           t.skill_id LIKE 'yingdao.%' OR
           EXISTS (SELECT 1 FROM task_shops ts WHERE ts.task_id = t.task_id)
         )
    """)
    op.execute("UPDATE schedules SET enabled = false, next_run_at = NULL WHERE enabled IS TRUE")
    op.execute("DELETE FROM device_provider_inventory WHERE provider_code = 'yingdao'")
    op.execute("DELETE FROM device_skill_capabilities WHERE skill_id LIKE 'yingdao.%' OR provider_code = 'yingdao'")
    op.drop_table("shop_credential_bindings")
    op.drop_table("platform_credentials")
    op.drop_table("shop_device_bindings")
    op.drop_table("shop_sessions")
    # These names make clear that the rows are historical only.  PostgreSQL
    # carries existing foreign keys along with each rename, preserving facts.
    op.rename_table("shops", "historical_shop_identities")
    op.rename_table("team_shop_accesses", "historical_team_shop_accesses")
    op.rename_table("task_shops", "historical_task_shop_refs")
    op.rename_table("schedule_shops", "historical_schedule_shop_refs")
    op.execute("""
        UPDATE api_tokens AS token
        SET permissions = COALESCE(
          (SELECT json_agg(item.value ORDER BY item.ordinality)
             FROM json_array_elements_text(token.permissions) WITH ORDINALITY AS item(value, ordinality)
            WHERE item.value NOT LIKE '% /api/v1/shops%'
              AND item.value NOT LIKE '% /api/v1/credentials%'
              AND item.value NOT LIKE '% /api/v1/automation-app-configs%'
              AND item.value NOT LIKE '% /api/v1/automation-parameter-presets%'), '[]'::json)
        WHERE EXISTS (
          SELECT 1 FROM json_array_elements_text(token.permissions) AS p(value)
          WHERE p.value LIKE '% /api/v1/shops%'
             OR p.value LIKE '% /api/v1/credentials%'
             OR p.value LIKE '% /api/v1/automation-app-configs%'
             OR p.value LIKE '% /api/v1/automation-parameter-presets%'
        )
    """)


def downgrade() -> None:
    raise RuntimeError("0056 removed central credentials; restore a verified backup to recover them")
