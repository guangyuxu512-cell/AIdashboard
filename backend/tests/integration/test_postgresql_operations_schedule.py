from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, time, timedelta
from threading import Barrier
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.models import Team
from app.modules.schedules.operations_models import OperationsSchedule, OperationsScheduleRun
from app.modules.schedules.operations_service import OperationsScheduleInput, get_schedule, put_schedule, send_pending, stage_due
from app.modules.users.models import User


pytestmark = pytest.mark.integration


@pytest.fixture
def state(postgresql_engine):
    team, other_team, user, strategy = uuid4(), uuid4(), uuid4(), uuid4()
    with Session(postgresql_engine) as session:
        session.add_all([Team(team_id=team, name='ops fixture'), Team(team_id=other_team, name='other fixture'),
                         User(user_id=user, display_name='ops fixture', is_super_account=True)])
        session.commit()
    actor = ActorContext(user, 'ops fixture', team, None, 'super_account', DataScope.ALL, True)
    yield postgresql_engine, actor, other_team, strategy
    with Session(postgresql_engine) as session:
        ids = session.scalars(select(OperationsSchedule.schedule_id).where(OperationsSchedule.team_id.in_([team, other_team]))).all()
        session.execute(delete(OperationsScheduleRun).where(OperationsScheduleRun.schedule_id.in_(ids)))
        session.execute(delete(OperationsSchedule).where(OperationsSchedule.team_id.in_([team, other_team])))
        session.execute(delete(User).where(User.user_id == user))
        session.execute(delete(Team).where(Team.team_id.in_([team, other_team])))
        session.commit()


def test_due_schedule_retries_one_idempotent_submission(state):
    engine, actor, other_team, strategy = state
    now = datetime(2026, 11, 20, 1, 0, tzinfo=UTC)
    rule = OperationsScheduleInput(name='fixture', enabled=True, kind='daily', local_time=time(10, 0))
    with Session(engine) as session:
        created = put_schedule(session, actor, strategy, rule, now=now)
        assert datetime.fromisoformat(created['next_run_at']).astimezone(UTC) == datetime(2026, 11, 20, 2, 0, tzinfo=UTC)
        other = ActorContext(actor.user_id, actor.user_display_name, other_team, None, actor.role_code, DataScope.TEAM, False)
        assert get_schedule(session, other, strategy) is None
    due = now + timedelta(hours=1)
    with Session(engine) as session:
        assert stage_due(session, now=due)
        assert not stage_due(session, now=due)
    submitted = []
    result_id = uuid4()
    def handler(request):
        submitted.append(__import__('json').loads(request.content))
        if len(submitted) == 1:
            return httpx.Response(503)
        return httpx.Response(202, json={'runId': str(result_id)})
    settings = Settings(operations_schedule_execution_enabled=True, operations_schedule_origin='https://ops.example.test',
                        operations_schedule_token='synthetic-service-token')
    with Session(engine) as session:
        assert send_pending(session, settings, now=due, transport=httpx.MockTransport(handler))
    with Session(engine) as session:
        assert not send_pending(session, settings, now=due, transport=httpx.MockTransport(handler))
        assert send_pending(session, settings, now=due + timedelta(seconds=10), transport=httpx.MockTransport(handler))
        record = session.scalars(select(OperationsScheduleRun)).one()
        assert (record.state, record.attempts, record.operations_run_id) == ('sent', 2, result_id)
    assert len(submitted) == 2 and submitted[0] == submitted[1]
    assert UUID(submitted[0]['strategyId']) == strategy


def test_disable_cancels_pending_without_touching_other_schedules(state):
    engine, actor, _other, strategy = state
    now = datetime(2026, 11, 20, 1, 0, tzinfo=UTC)
    with Session(engine) as session:
        put_schedule(session, actor, strategy, OperationsScheduleInput(name='fixture', enabled=True, kind='hourly', interval_hours=1), now=now)
    with Session(engine) as session:
        assert stage_due(session, now=now + timedelta(hours=1))
    with Session(engine) as session:
        put_schedule(session, actor, strategy, OperationsScheduleInput(name='fixture', enabled=False, kind='hourly', interval_hours=1), now=now + timedelta(hours=1))
        record = session.scalars(select(OperationsScheduleRun)).one()
        assert (record.state, record.error_code) == ('cancelled', 'SCHEDULE_DISABLED')
        assert get_schedule(session, actor, strategy)['next_run_at'] is None


def test_concurrent_scanners_stage_only_one_occurrence(state):
    engine, actor, _other, strategy = state
    now = datetime(2026, 11, 20, 1, 0, tzinfo=UTC)
    with Session(engine) as session:
        put_schedule(session, actor, strategy, OperationsScheduleInput(name='fixture', enabled=True, kind='hourly', interval_hours=1), now=now)
    barrier = Barrier(2)
    def scan(_):
        with Session(engine) as session:
            barrier.wait(timeout=10)
            return stage_due(session, now=now + timedelta(hours=1))
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(scan, range(2))) == 1
    with Session(engine) as session:
        assert len(session.scalars(select(OperationsScheduleRun)).all()) == 1


def test_existing_scheduler_triggers_operations_at_the_due_time(state, monkeypatch):
    from app.modules.schedules import scheduler

    engine, actor, _other, strategy = state
    now = datetime(2026, 11, 20, 1, 0, tzinfo=UTC)
    with Session(engine) as session:
        put_schedule(session, actor, strategy, OperationsScheduleInput(name='fixture', enabled=True, kind='hourly', interval_hours=1), now=now)
    settings = Settings(worker_schedule_execution_enabled=True, operations_schedule_execution_enabled=True,
                        operations_schedule_origin='https://ops.example.test', operations_schedule_token='synthetic-service-token')
    result_id, calls = uuid4(), []
    transport = httpx.MockTransport(lambda request: (calls.append(request) or httpx.Response(202, json={'runId': str(result_id)})))
    real_send = scheduler.send_pending
    monkeypatch.setattr(scheduler, 'get_settings', lambda: settings)
    monkeypatch.setattr(scheduler, 'get_session_factory', lambda: lambda: Session(engine))
    monkeypatch.setattr(scheduler, 'send_pending', lambda session, settings, now=None: real_send(session, settings, now=now, transport=transport))
    class NoLegacyDispatch:
        def __init__(self, _session): pass
        def trigger_next_due(self, *, now=None): return None
    # Existing Integration schedules are user data; the test must not run them.
    monkeypatch.setattr(scheduler, 'ScheduleService', NoLegacyDispatch)
    assert scheduler.trigger_due_schedules_once(now=now + timedelta(minutes=59)) == 0
    assert scheduler.trigger_due_schedules_once(now=now + timedelta(hours=1)) == 1
    assert scheduler.trigger_due_schedules_once(now=now + timedelta(hours=1)) == 0
    with Session(engine) as session:
        run = session.scalars(select(OperationsScheduleRun)).one()
        assert run.state == 'sent' and run.operations_run_id == result_id
    assert len(calls) == 1
