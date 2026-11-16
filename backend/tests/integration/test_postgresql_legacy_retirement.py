"""The 0056 migration must not stop live Workers when retiring old tasks."""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


def test_legacy_retirement_only_retires_long_offline_unleased_tasks(postgresql_engine):
    migration = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261116_0056_retire_central_shop_control.py"
    spec = importlib.util.spec_from_file_location("retirement_0056", migration)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Temporary tables shadow real tables only on this connection.
    with postgresql_engine.begin() as connection:
        connection.execute(text("""
            CREATE TEMP TABLE tasks (
              task_id text PRIMARY KEY, target_device_id text, status text, skill_id text,
              lease_until timestamptz, started_at timestamptz, created_at timestamptz,
              error_code text, error_message text, finished_at timestamptz, updated_at timestamptz
            ) ON COMMIT DROP
        """))
        connection.execute(text("CREATE TEMP TABLE task_shops (task_id text) ON COMMIT DROP"))
        connection.execute(text("""
            CREATE TEMP TABLE device_runtime (
              device_id text, connection_status text, last_seen_at timestamptz
            ) ON COMMIT DROP
        """))
        connection.execute(text("""
            INSERT INTO device_runtime VALUES
              ('old-offline', 'offline', now() - interval '2 days'),
              ('old-online', 'online', now() - interval '2 days'),
              ('recent-offline', 'offline', now() - interval '2 minutes')
        """))
        connection.execute(text("""
            INSERT INTO tasks(task_id,target_device_id,status,skill_id,lease_until,started_at,created_at)
            VALUES
              ('retire', 'old-offline', 'running', 'yingdao.app.run', NULL, now()-interval '2 days', now()-interval '2 days'),
              ('online', 'old-online', 'running', 'yingdao.app.run', NULL, now()-interval '2 days', now()-interval '2 days'),
              ('recent', 'recent-offline', 'running', 'yingdao.app.run', NULL, now()-interval '2 days', now()-interval '2 days'),
              ('leased', 'old-offline', 'running', 'yingdao.app.run', now()+interval '1 hour', now()-interval '2 days', now()-interval '2 days'),
              ('ordinary', 'old-offline', 'running', 'system.echo', NULL, now()-interval '2 days', now()-interval '2 days'),
              ('bound', 'old-offline', 'running', 'system.echo', NULL, now()-interval '2 days', now()-interval '2 days'),
              ('pending', 'old-offline', 'pending', 'yingdao.app.run', NULL, NULL, now()-interval '2 days')
        """))
        connection.execute(text("INSERT INTO task_shops VALUES ('bound')"))
        connection.execute(text(module.RETIRE_STALE_UNLEASED_TASKS_SQL))
        rows = dict(connection.execute(text("SELECT task_id, status FROM tasks")).all())
        assert rows == {
            "retire": "lost", "bound": "lost", "online": "running",
            "recent": "running", "leased": "running", "ordinary": "running",
            "pending": "pending",
        }
        assert connection.scalar(text("SELECT error_code FROM tasks WHERE task_id='retire'")) == "LEGACY_UNLEASED_TASK_RETIRED"
