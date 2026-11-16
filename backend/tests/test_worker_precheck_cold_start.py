"""Exercise task creation with the production application's import graph."""

import os
from pathlib import Path
import subprocess
import sys


def test_fresh_process_can_create_worker_task_without_legacy_routes(tmp_path: Path) -> None:
    # A separate interpreter prevents other tests from accidentally registering
    # historical ORM models before the application starts.
    code = r'''
from uuid import uuid4

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.main import app
from app.modules.schedules.models import Schedule
from app.modules.tasks.models import Task

assert not any(path.startswith("/api/v1/automation-app-configs") for path in app.openapi()["paths"])
assert not any(path.startswith("/api/v1/automation-parameter-presets") for path in app.openapi()["paths"])

engine = create_engine("sqlite:///:memory:")
with engine.begin() as connection:
    connection.exec_driver_sql("""CREATE TABLE tasks (
        task_id CHAR(32) PRIMARY KEY, team_id CHAR(32) NOT NULL, target_device_id CHAR(32) NOT NULL,
        created_by_user_id CHAR(32), parameter_preset_id CHAR(32), parameter_preset_version INTEGER,
        skill_id VARCHAR(200) NOT NULL, execution_display_name VARCHAR(500) NOT NULL, status VARCHAR(8) NOT NULL,
        input_json TEXT NOT NULL, result_json TEXT, error_code VARCHAR(64), error_message TEXT,
        lease_until DATETIME, started_at DATETIME, finished_at DATETIME, runtime_events_purged_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
    )""")
with Session(engine) as session:
    session.add(Task(task_id=uuid4(), team_id=uuid4(), target_device_id=uuid4(),
                     skill_id="douyin.category_schema", execution_display_name="precheck",
                     status="pending", input_json={"category_id": "0"}))
    session.flush()
    session.rollback()

# Future scheduled tasks must also resolve the retained historical reference.
inspect(Schedule)._sorted_tables
'''
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    for key in ("DATABASE_URL", "BACKEND_DATABASE_URL"):
        env.pop(key, None)
    completed = subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path, env=env,
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stderr
