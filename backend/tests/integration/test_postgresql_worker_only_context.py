import asyncio
from contextlib import suppress
from datetime import UTC, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.models import Team, TeamDeviceAccess
from app.modules.devices.models import Device
from app.modules.schedules.models import Schedule, ScheduleRun
from app.modules.schedules.schemas import ScheduleCreate
from app.modules.schedules.service import ScheduleService
from app.modules.schedules import scheduler
from app.modules.tasks.exceptions import TaskInputInvalidError
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import TaskCreate, WorkerTaskRead
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workers.models import DeviceRuntime, DeviceSkillCapability
from app.modules.workers.precheck_models import WorkerRpaShopInventory
from app.modules.workers.service import WorkerPrincipal, WorkerService


pytestmark = pytest.mark.integration


@pytest.fixture
def worker_context(postgresql_engine):
    engine = postgresql_engine
    team_id, user_id, device_id, install_id = (uuid4() for _ in range(4))
    now = datetime.now(UTC)
    actor = ActorContext(user_id=user_id, user_display_name='fixture', team_id=team_id,
                         membership_id=uuid4(), role_code='member', data_scope=DataScope.TEAM)
    with Session(engine) as session:
        session.add_all([Team(team_id=team_id, name='worker context fixture'),
                         User(user_id=user_id, display_name='worker context fixture')])
        session.flush()
        session.add(Device(device_id=device_id, team_id=team_id, display_name='fixture'))
        session.flush()
        session.add_all([
            TeamDeviceAccess(team_id=team_id, device_id=device_id),
            DeviceRuntime(device_id=device_id, worker_version='0.5.7', started_at=now,
                          last_seen_at=now, connection_status='online'),
            DeviceSkillCapability(device_id=device_id, skill_id='system.echo', display_name='echo',
                                  runtime='python', skill_version='1', classification='internal'),
            DeviceSkillCapability(device_id=device_id, skill_id='catalog.fixture.run', display_name='业务技能',
                runtime='python', skill_version='1', classification='business', input_schema={
                    'type': 'object', 'properties': {'message': {'type': 'string'}},
                    'required': ['message'], 'additionalProperties': False}),
            WorkerRpaShopInventory(device_id=device_id, installation_id=install_id, available=True,
                last_discovered_at=now, shops=[{'localShopId':'local-1', 'platformShopId':'123',
                                                'shopName':'fixture', 'platform':'douyin'}]),
        ])
        session.commit()
    yield engine, actor, device_id
    with Session(engine) as session:
        schedule_ids = session.query(Schedule.schedule_id).filter_by(target_device_id=device_id).all()
        if schedule_ids:
            session.execute(delete(ScheduleRun).where(ScheduleRun.schedule_id.in_([v[0] for v in schedule_ids])))
        session.execute(delete(Schedule).where(Schedule.target_device_id == device_id))
        session.execute(delete(Task).where(Task.target_device_id == device_id))
        session.execute(delete(WorkerRpaShopInventory).where(WorkerRpaShopInventory.device_id == device_id))
        session.execute(delete(DeviceSkillCapability).where(DeviceSkillCapability.device_id == device_id))
        session.execute(delete(DeviceRuntime).where(DeviceRuntime.device_id == device_id))
        session.execute(delete(TeamDeviceAccess).where(TeamDeviceAccess.device_id == device_id))
        session.execute(delete(Device).where(Device.device_id == device_id))
        session.execute(delete(User).where(User.user_id == user_id))
        session.execute(delete(Team).where(Team.team_id == team_id))
        session.commit()


def test_task_uses_only_its_workers_inventory_and_rechecks_identity(worker_context):
    engine, actor, device_id = worker_context
    with Session(engine, expire_on_commit=False) as session:
        service = TaskService(session)
        with pytest.raises(TaskInputInvalidError):
            service.create(TaskCreate(target_device_id=device_id, skill_id='system.echo',
                local_shop_ids=['not-on-this-device'], input={'message':'test'}), actor)
        session.rollback()
        task = service.create(TaskCreate(target_device_id=device_id, skill_id='system.echo',
            local_shop_ids=['local-1'], input={'message':'test'}), actor)
        claimed = service.claim_with_context(WorkerPrincipal(device_id=device_id))
        assert claimed is not None and claimed.task.task_id == task.task_id
        assert claimed.local_shops == [{'local_shop_id':'local-1', 'platform':'douyin', 'platform_shop_id':'123'}]
        assert not claimed.task.shop_ids
        assert 'cookie' not in repr(claimed.local_shops).lower()
        claimed.task.status = 'success'
        claimed.task.finished_at = datetime.now(UTC)
        session.commit()
        stale = service.create(TaskCreate(target_device_id=device_id, skill_id='system.echo',
            local_shop_ids=['local-1'], input={'message':'test'}), actor)
        inventory = session.get(WorkerRpaShopInventory, device_id)
        inventory.shops = [{'localShopId':'local-1', 'platformShopId':'other', 'platform':'douyin'}]
        session.commit()
        assert service.claim_with_context(WorkerPrincipal(device_id=device_id)) is None
        assert session.get(Task, stale.task_id).error_code == 'WORKER_SHOP_MAPPING_CHANGED'


def test_old_worker_can_claim_precheck_without_new_payload_field(worker_context):
    engine, actor, device_id = worker_context
    with Session(engine, expire_on_commit=False) as session:
        session.get(DeviceRuntime, device_id).worker_version = '0.5.5'
        service = TaskService(session)
        mapped = service.create(TaskCreate(target_device_id=device_id, skill_id='system.echo',
            local_shop_ids=['local-1'], input={'message':'test'}), actor)
        precheck = Task(team_id=actor.team_id, created_by_user_id=actor.user_id,
            target_device_id=device_id, skill_id='douyin.category_schema', execution_display_name='fixture',
            status='pending', input_json={'platform_shop_id':'123'})
        session.add(precheck)
        session.commit()
        claimed = service.claim_with_context(WorkerPrincipal(device_id=device_id))
        assert claimed is not None and claimed.task.task_id == precheck.task_id
        assert session.get(Task, mapped.task_id).status == 'pending'
        payload = WorkerTaskRead(task_id=precheck.task_id, skill_id=precheck.skill_id,
            input={}, lease_until=claimed.task.lease_until, local_shops=[]).model_dump(exclude_defaults=True)
        assert 'local_shops' not in payload


def test_schedule_uses_local_shops_and_is_disabled_by_default_in_form(worker_context):
    engine, actor, device_id = worker_context
    with Session(engine) as session:
        plan = ScheduleService(session).create(ScheduleCreate(name='fixture', target_device_id=device_id,
            local_shop_ids=['local-1'], skill_id='system.echo', parameters={'message':'test'},
            local_time=time(9, 0), timezone='Asia/Shanghai', enabled=False), actor)
        assert plan.local_shop_ids == ['local-1']
        assert plan.shop_ids == [] and plan.enabled is False and plan.next_run_at is None
        with pytest.raises(ValueError):
            ScheduleCreate(name='legacy', target_device_id=device_id, execution_type='yingdao_application',
                           application_id='legacy', local_time=time(9, 0), timezone='Asia/Shanghai')


def test_enabled_worker_scheduler_dispatches_once_without_old_plans(worker_context, monkeypatch):
    engine, actor, device_id = worker_context
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    due = now + timedelta(minutes=2)
    local_due = due.astimezone(ZoneInfo('Asia/Shanghai'))
    with Session(engine) as session:
        catalog = WorkerService(session).get_business_skill_catalog(device_id)
        assert [(item.skill_id, item.availability) for item in catalog] == [
            ('catalog.fixture.run', 'available')]
        plan = ScheduleService(session).create(ScheduleCreate(
            name='new worker fixture', target_device_id=device_id, local_shop_ids=['local-1'],
            skill_id='catalog.fixture.run', parameters={'message': 'safe'}, schedule_type='once',
            local_date=local_due.date(), local_time=local_due.time().replace(tzinfo=None),
            timezone='Asia/Shanghai', enabled=True), actor, now=now)
        legacy = Schedule(team_id=actor.team_id, created_by_user_id=actor.user_id,
            name='legacy yingdao fixture', enabled=True, target_device_id=device_id,
            skill_id='yingdao.app.run', execution_display_name='legacy', schedule_type='once',
            local_date=local_due.date(), local_time=local_due.time().replace(tzinfo=None),
            timezone='Asia/Shanghai', task_input_json={}, next_run_at=now)
        disabled = Schedule(team_id=actor.team_id, created_by_user_id=actor.user_id,
            name='disabled old worker fixture', enabled=False, target_device_id=device_id,
            skill_id='catalog.fixture.run', execution_display_name='old', schedule_type='once',
            local_date=local_due.date(), local_time=local_due.time().replace(tzinfo=None),
            timezone='Asia/Shanghai', task_input_json={'message': 'old'}, next_run_at=now)
        session.add_all([legacy, disabled])
        session.commit()
        legacy_id, disabled_id = legacy.schedule_id, disabled.schedule_id

    monkeypatch.setenv('BACKEND_WORKER_SCHEDULE_EXECUTION_ENABLED', 'true')
    monkeypatch.setenv('BACKEND_PRODUCT_SELECTION_EXECUTION_ENABLED', 'true')
    monkeypatch.setenv('BACKEND_PRODUCT_SELECTION_SCHEDULE_ENABLED', 'true')
    get_settings.cache_clear()
    monkeypatch.setattr(scheduler, 'get_session_factory', lambda: sessionmaker(bind=engine))
    assert not hasattr(scheduler, 'SelectionScheduleService')
    try:
        assert scheduler.trigger_due_schedules_once(now=due - timedelta(seconds=1)) == 0
        assert scheduler.trigger_due_schedules_once(now=due) == 1
        assert scheduler.trigger_due_schedules_once(now=due) == 0
        with Session(engine) as session:
            runs = list(session.scalars(select(ScheduleRun).where(
                ScheduleRun.schedule_id.in_([plan.schedule_id, legacy_id, disabled_id]))))
            assert len(runs) == 1 and runs[0].schedule_id == plan.schedule_id
            task = session.get(Task, runs[0].task_id)
            assert task is not None and task.status == 'pending' and task.skill_id == 'catalog.fixture.run'
            claimed = TaskService(session).claim_with_context(WorkerPrincipal(device_id=device_id), now=due)
            assert claimed is not None and claimed.task.task_id == task.task_id
            assert claimed.local_shops == [{'local_shop_id': 'local-1', 'platform': 'douyin',
                                            'platform_shop_id': '123'}]
    finally:
        get_settings.cache_clear()


def test_worker_scheduler_loop_dispatches_at_actual_due_time(worker_context, monkeypatch):
    engine, actor, device_id = worker_context
    now = datetime.now(UTC)
    # ScheduleCreate normalizes wall time to the minute; leave enough time to
    # start the loop before the next selected minute even on a slow database.
    due = (now + timedelta(seconds=70)).replace(second=0, microsecond=0)
    local_due = due.astimezone(ZoneInfo('Asia/Shanghai'))
    with Session(engine) as session:
        plan = ScheduleService(session).create(ScheduleCreate(
            name='wall clock worker fixture', target_device_id=device_id, local_shop_ids=['local-1'],
            skill_id='catalog.fixture.run', parameters={'message': 'safe'}, schedule_type='once',
            local_date=local_due.date(), local_time=local_due.time().replace(tzinfo=None),
            timezone='Asia/Shanghai', enabled=True), actor, now=now)

    monkeypatch.setenv('BACKEND_WORKER_SCHEDULE_EXECUTION_ENABLED', 'true')
    monkeypatch.setenv('BACKEND_SCHEDULE_SCAN_INTERVAL_SECONDS', '1')
    monkeypatch.setattr(scheduler, 'get_session_factory', lambda: sessionmaker(bind=engine))
    get_settings.cache_clear()

    async def observe():
        loop = asyncio.create_task(scheduler.trigger_due_schedules_forever())
        try:
            deadline = asyncio.get_running_loop().time() + 90
            while asyncio.get_running_loop().time() < deadline:
                with Session(engine) as session:
                    run = session.scalar(select(ScheduleRun).where(ScheduleRun.schedule_id == plan.schedule_id))
                    if run is not None:
                        assert datetime.now(UTC) >= due
                        assert run.scheduled_for == due
                        claimed = TaskService(session).claim_with_context(
                            WorkerPrincipal(device_id=device_id))
                        assert claimed is not None and claimed.task.task_id == run.task_id
                        return
                await asyncio.sleep(0.5)
            pytest.fail('worker scheduler did not dispatch the due plan')
        finally:
            loop.cancel()
            with suppress(asyncio.CancelledError):
                await loop

    try:
        asyncio.run(observe())
    finally:
        get_settings.cache_clear()
