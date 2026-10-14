"""0046 actual Feature lifecycle/metadata. No platform or other environment."""
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import MetaData, delete, text
from sqlalchemy.orm import Session
import pytest

from app.core.database import Base
from app.modules.devices.models import Device
from app.modules.schedules.models import Schedule, ScheduleRun
from app.modules.product_selection.models import (
    ProductSelectionCandidate, ProductSelectionObservation, ProductSelectionRun,
    ProductSelectionStrategy, ProductSelectionResultItem,
)
from tests.integration.test_postgresql_product_selection import selection_context, _save
from tests.integration.test_postgresql_selection_strategies import _save as save_strategy

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def test_0046_metadata_matches_declared_models(postgresql_engine):
    models = (ProductSelectionCandidate, ProductSelectionObservation, ProductSelectionRun, ProductSelectionStrategy, ProductSelectionResultItem)
    names = {model.__tablename__ for model in models}
    metadata = MetaData(naming_convention=Base.metadata.naming_convention)
    with postgresql_engine.connect() as connection:
        metadata.reflect(bind=connection, only=["users", "teams", "shops"])
        for model in models:
            model.__table__.to_metadata(metadata)
        def include_object(obj, name, kind, reflected, compare_to):
            return name in names if kind == "table" else getattr(getattr(obj, "table", None), "name", None) in names
        context = MigrationContext.configure(connection, opts={"include_object": include_object})
        assert compare_metadata(context, metadata) == []


def test_0046_roundtrip_preserves_old_facts_b_and_pc(selection_context, postgresql_url):
    context = selection_context
    assert postgresql_url.database == "control_center_feat_product_selection"
    observation_id = _save(context)[0]  # legacy untracked fact with no new semantics
    strategy = save_strategy(context, schedule={"scheduled": True, "kind": "hourly", "interval_hours": 5})
    device_id, pc_id, pc_run = uuid4(), uuid4(), uuid4()
    with Session(context[0]) as session:
        session.add(Device(device_id=device_id, team_id=context[1][0], display_name="stage-2a1 0046 preserved PC"))
        session.flush()
        session.add(Schedule(schedule_id=pc_id, team_id=context[1][0], created_by_user_id=context[2][0], name="stage-2a1 0046 PC",
            target_device_id=device_id, enabled=True, skill_id="system.echo", execution_display_name="旧PC",
            schedule_type="weekly", local_time=time(9, 17), timezone="Asia/Shanghai", weekdays=[1, 4],
            task_input_json={"message": "preserve"}, next_run_at=datetime.now(UTC) + timedelta(days=1)))
        session.flush()
        session.add(ScheduleRun(run_id=pc_run, schedule_id=pc_id, scheduled_for=datetime.now(UTC), trigger_result="blocked",
            trigger_error_code="SAFE_PC_FIXTURE"))
        session.commit()
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.hide_parameters", "true")
    queries = {
        "observation": "SELECT title,category_path,rank,checked_at,metrics_retrieved_at,last_attempt_at,source_context FROM product_selection_observations WHERE observation_id=:observation",
        "plans": "SELECT schedule_id,name,enabled,target_kind,selection_strategy_id,target_device_id,schedule_type,interval_hours,next_run_at,local_time,weekdays,task_input_json FROM schedules WHERE team_id=:team ORDER BY schedule_id",
        "pc_run": "SELECT scheduled_for,trigger_result,trigger_error_code FROM schedule_runs WHERE run_id=:run",
    }
    args = {"observation": observation_id, "team": context[1][0], "run": pc_run}
    def snapshot():
        with context[0].connect() as connection:
            return {name: connection.execute(text(query), args).all() for name, query in queries.items()}
    before = snapshot()
    try:
        command.downgrade(config, "20261013_0045")
        assert before == snapshot()
    finally:
        command.upgrade(config, "head")
        with Session(context[0]) as session:
            session.execute(delete(ScheduleRun).where(ScheduleRun.run_id == pc_run))
            session.execute(delete(Schedule).where(Schedule.schedule_id == pc_id))
            session.execute(delete(Device).where(Device.device_id == device_id))
            session.commit()
    after = snapshot()
    assert before["observation"] == after["observation"]
    assert len(before["plans"]) == 2 and len(after["plans"]) == 1  # only synthetic PC explicitly removed
    with context[0].connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20261015_0046"

