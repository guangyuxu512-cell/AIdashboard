"""0045 actual PostgreSQL shapes and preservation, no platform calls."""

from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import text, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.product_selection.models import ProductSelectionStrategy as Strategy
from app.modules.schedules.models import Schedule, ScheduleRun
from app.modules.devices.models import Device
from tests.integration.test_postgresql_product_selection import selection_context, _save as save_fact
from tests.integration.test_postgresql_selection_strategies import _config, _save as save_strategy

pytestmark = pytest.mark.integration


def plan(context, sid, **changes):
    return Schedule(**({
        'schedule_id': uuid4(), 'team_id': context[1][0], 'created_by_user_id': context[2][0],
        'name': 'stage-2a1 schema', 'enabled': False, 'target_kind': 'server_selection',
        'selection_strategy_id': sid, 'target_device_id': None, 'skill_id': None,
        'execution_display_name': 'stage-2a1 selection', 'schedule_type': 'hourly',
        'local_time': None, 'interval_hours': 3, 'timezone': 'Asia/Shanghai',
        'local_date': None, 'weekdays': [], 'task_input_json': {}, 'next_run_at': None,
    } | changes))


@pytest.mark.parametrize('changes,constraint', [
    ({'interval_hours': None}, 'ck_schedules_time_fields'),
    ({'interval_hours': 0}, 'ck_schedules_time_fields'),
    ({'interval_hours': -1}, 'ck_schedules_time_fields'),
    ({'local_time': time(0)}, 'ck_schedules_time_fields'),
    ({'schedule_type': 'daily', 'interval_hours': 2, 'local_time': time(9)}, 'ck_schedules_time_fields'),
    ({'schedule_type': 'daily', 'interval_hours': None}, 'ck_schedules_time_fields'),
    ({'weekdays': [1]}, 'ck_schedules_rule_fields'),
    ({'timezone': 'UTC'}, 'ck_schedules_target_fields'),
    ({'skill_id': 'system.echo'}, 'ck_schedules_target_fields'),
    ({'selection_strategy_id': None}, 'ck_schedules_target_fields'),
    ({'target_kind': 'pc'}, 'ck_schedules_target_fields'),
])
def test_explicit_null_and_target_checks_reject_invalid_shape(selection_context, changes, constraint):
    context = selection_context
    saved = save_strategy(context, schedule={'scheduled':False})
    with Session(context[0]) as session:
        session.add(plan(context, saved.strategy_id, **changes))
        with pytest.raises(IntegrityError) as failure:
            session.flush()
        assert failure.value.orig.diag.constraint_name == constraint
        session.rollback()


def test_hourly_daily_unique_and_restrict_relationship(selection_context):
    context = selection_context
    saved, daily = save_strategy(context, schedule={'scheduled':False}), save_strategy(context, schedule={'scheduled':False})
    with Session(context[0]) as session:
        hourly = plan(context, saved.strategy_id)
        session.add_all([hourly, plan(context, daily.strategy_id, schedule_type='daily', interval_hours=None, local_time=time(9))])
        session.commit()
        session.add(plan(context, saved.strategy_id))
        with pytest.raises(IntegrityError) as failure: session.flush()
        assert failure.value.orig.diag.constraint_name == 'uq_schedules_selection_strategy'
        session.rollback()
        session.delete(session.get(Strategy, saved.strategy_id))
        with pytest.raises(IntegrityError) as failure: session.flush()
        assert failure.value.orig.diag.constraint_name == 'fk_schedules_selection_strategy'
        session.rollback()
        hourly.deleted_at = hourly.created_at
        session.add(hourly); session.commit()
        session.add(plan(context, saved.strategy_id)); session.commit()


def test_0045_roundtrip_preserves_existing_a_facts_and_strategy(selection_context, postgresql_url):
    context = selection_context
    assert postgresql_url.database == 'control_center_feat_product_selection'
    observation = save_fact(context)[0]
    # This is existing A data, not a new B schedule to delete for a downgrade.
    cfg = _config(context)
    sid, device_id, pc_id, pc_run_id = uuid4(), uuid4(), uuid4(), uuid4()
    with Session(context[0]) as session:
        session.add(Strategy(strategy_id=sid, team_id=context[1][0], created_by_user_id=context[2][0], request_shop_id=context[3][0], name=cfg.name, enabled=True, version=1, conditions=cfg.conditions.model_dump(mode='json'), schedule_config=cfg.schedule.model_dump(mode='json')))
        session.add(Device(device_id=device_id, team_id=context[1][0], display_name='stage-2a1 preserved PC'))
        session.flush()
        session.add(Schedule(schedule_id=pc_id, team_id=context[1][0], created_by_user_id=context[2][0], name='stage-2a1 old PC', enabled=True, target_device_id=device_id, skill_id='system.echo', execution_display_name='旧PC', schedule_type='weekly', local_time=time(9, 17), timezone='Asia/Shanghai', local_date=None, weekdays=[1, 4], task_input_json={'message':'preserve'}, next_run_at=datetime.now(UTC)+timedelta(days=1)))
        session.flush()
        session.add(ScheduleRun(run_id=pc_run_id, schedule_id=pc_id, scheduled_for=datetime.now(UTC), trigger_result='blocked', task_id=None, trigger_error_code='SAFE_PC_FIXTURE', trigger_error_message=None))
        session.commit()
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / 'alembic.ini')); config.set_main_option('script_location', str(root / 'migrations'))
    config.set_main_option('sqlalchemy.hide_parameters', 'true')
    pc_fields = 'name,enabled,target_device_id,skill_id,execution_display_name,schedule_type,local_time,timezone,local_date,weekdays,task_input_json,next_run_at,team_id,created_by_user_id,created_at,updated_at'
    with context[0].connect() as connection:
        pc_values = tuple(connection.execute(text('SELECT '+pc_fields+' FROM schedules WHERE schedule_id=:key'), {'key':pc_id}).one())
    try:
        command.downgrade(config, '20261013_0044')
        with context[0].connect() as connection:
            assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '20261013_0044'
            assert connection.scalar(text('SELECT observation_id FROM product_selection_observations WHERE observation_id=:key'), {'key': observation}) == observation
            assert connection.scalar(text('SELECT strategy_id FROM product_selection_strategies WHERE strategy_id=:key'), {'key': sid}) == sid
            assert tuple(connection.execute(text('SELECT '+pc_fields+' FROM schedules WHERE schedule_id=:key'), {'key':pc_id}).one()) == pc_values
            assert connection.scalar(text('SELECT trigger_error_code FROM schedule_runs WHERE run_id=:key'), {'key':pc_run_id}) == 'SAFE_PC_FIXTURE'
    finally:
        command.upgrade(config, 'head')
        with Session(context[0]) as session:
            assert tuple(session.execute(text('SELECT '+pc_fields+' FROM schedules WHERE schedule_id=:key'), {'key':pc_id}).one()) == pc_values
            session.execute(delete(ScheduleRun).where(ScheduleRun.run_id==pc_run_id))
            session.execute(delete(Schedule).where(Schedule.schedule_id==pc_id))
            session.execute(delete(Device).where(Device.device_id==device_id)); session.commit()
    with Session(context[0]) as session:
        assert session.get(Strategy, sid).version == 1
        assert session.scalar(text('SELECT version_num FROM alembic_version')) == '20261013_0045'


def test_0045_with_server_history_refuses_downgrade(selection_context, postgresql_url):
    context = selection_context
    saved = save_strategy(context, schedule={'scheduled':False})
    with Session(context[0]) as session:
        session.add(plan(context, saved.strategy_id)); session.commit()
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / 'alembic.ini')); config.set_main_option('script_location', str(root / 'migrations'))
    with pytest.raises(RuntimeError, match='retain schema'):
        command.downgrade(config, '20261013_0044')
    with Session(context[0]) as session:
        assert session.scalar(text('SELECT version_num FROM alembic_version')) == '20261013_0045'
