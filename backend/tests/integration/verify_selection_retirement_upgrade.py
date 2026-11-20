"""Verify the destructive upgrade only in its explicitly named disposable DB."""
from pathlib import Path
import sys
from uuid import uuid4

from alembic import command
from alembic.config import Config
from psycopg import connect
from psycopg.types.json import Json, Jsonb
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
from app.core.config import get_settings
url = make_url(str(get_settings().database_url))
if url.database != "control_center_feat_retire_selection_upgrade":
    raise RuntimeError("This check requires its dedicated disposable Feature database")
dsn = url.set(drivername="postgresql").render_as_string(hide_password=False)
with connect(dsn, connect_timeout=5) as connection:
    assert connection.execute("SELECT current_database()").fetchone()[0] == url.database
    assert connection.execute("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'").fetchone()[0] == 0

config = Config(str(BACKEND / "alembic.ini"))
config.set_main_option("script_location", str(BACKEND / "migrations"))
command.upgrade(config, "20261120_0057")
ids = {name: str(uuid4()) for name in (
    "team", "user", "device", "shop", "strategy", "old_schedule", "pc_schedule",
    "old_run", "pc_run", "ops_schedule", "token",
)}
with connect(dsn, connect_timeout=5) as connection:
    connection.execute("INSERT INTO teams(team_id,name) VALUES (%s,%s)", (ids["team"], "fixture"))
    connection.execute("INSERT INTO users(user_id,display_name) VALUES (%s,%s)", (ids["user"], "fixture"))
    connection.execute("INSERT INTO devices(device_id,team_id,display_name) VALUES (%s,%s,%s)",
                       (ids["device"], ids["team"], "fixture"))
    connection.execute("INSERT INTO historical_shop_identities(shop_id,display_name,platform) VALUES (%s,%s,%s)",
                       (ids["shop"], "fixture", "douyin"))
    connection.execute("""INSERT INTO product_selection_strategies
        (strategy_id,team_id,created_by_user_id,request_shop_id,name,version,enabled,conditions,schedule_config)
        VALUES (%s,%s,%s,%s,%s,1,false,%s,%s)""",
        (ids["strategy"], ids["team"], ids["user"], ids["shop"], "fixture", Jsonb({}), Jsonb({})))
    connection.execute("""INSERT INTO schedules(schedule_id,team_id,created_by_user_id,name,enabled,
        target_kind,selection_strategy_id,execution_display_name,schedule_type,timezone,interval_hours,task_input_json)
        VALUES (%s,%s,%s,%s,false,'server_selection',%s,%s,'hourly','Asia/Shanghai',1,%s)""",
        (ids["old_schedule"], ids["team"], ids["user"], "old-fixture", ids["strategy"], "old", Jsonb({})))
    connection.execute("""INSERT INTO schedules(schedule_id,team_id,created_by_user_id,name,enabled,
        target_device_id,skill_id,execution_display_name,schedule_type,local_time,timezone,task_input_json)
        VALUES (%s,%s,%s,%s,true,%s,'system.echo',%s,'daily','09:00','Asia/Shanghai',%s)""",
        (ids["pc_schedule"], ids["team"], ids["user"], "pc-fixture", ids["device"], "pc", Jsonb({"fixture": True})))
    for key, schedule in (("old_run", "old_schedule"), ("pc_run", "pc_schedule")):
        connection.execute("INSERT INTO schedule_runs(run_id,schedule_id,scheduled_for,trigger_result) "
                           "VALUES (%s,%s,now(),'blocked')", (ids[key], ids[schedule]))
    connection.execute("""INSERT INTO operations_selection_schedules
        (schedule_id,team_id,created_by_user_id,strategy_id,name,enabled,kind,local_time)
        VALUES (%s,%s,%s,%s,%s,false,'daily','09:00')""",
        (ids["ops_schedule"], ids["team"], ids["user"], str(uuid4()), "ops-fixture"))
    connection.execute("INSERT INTO team_module_accesses(team_id,module_code) VALUES (%s,%s),(%s,%s)",
                       (ids["team"], "product-selection", ids["team"], "device"))
    connection.execute("INSERT INTO api_tokens(token_id,owner_user_id,name,token_hash,permissions) "
                       "VALUES (%s,%s,%s,%s,%s)", (ids["token"], ids["user"], "fixture", "0" * 64,
                       Json(["GET /api/v1/product-selection/runs", "GET /api/v1/devices"])))

command.upgrade(config, "head")
with connect(dsn, connect_timeout=5) as connection:
    assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "20261121_0058"
    assert connection.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public' "
                              "AND tablename LIKE 'product_selection_%'").fetchone()[0] == 0
    assert connection.execute("SELECT count(*) FROM schedules WHERE schedule_id=%s AND target_kind='pc'",
                              (ids["pc_schedule"],)).fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM schedule_runs WHERE run_id=%s", (ids["pc_run"],)).fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM operations_selection_schedules WHERE schedule_id=%s",
                              (ids["ops_schedule"],)).fetchone()[0] == 1
    assert connection.execute("SELECT module_code FROM team_module_accesses WHERE team_id=%s",
                              (ids["team"],)).fetchall() == [("device",)]
    assert connection.execute("SELECT permissions FROM api_tokens WHERE token_id=%s",
                              (ids["token"],)).fetchone()[0] == ["GET /api/v1/devices"]
print("retired-selection upgrade preserved Worker and Operations schedules")
