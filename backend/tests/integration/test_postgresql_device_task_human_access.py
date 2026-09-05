from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete, inspect, make_url, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_database_engine
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.devices.exceptions import DeviceNotFoundError
from app.modules.devices.models import Device
from app.modules.devices.schemas import DeviceCreate, DeviceUpdate
from app.modules.devices.service import DeviceService
from app.modules.schedules.enums import ScheduleExecutionType, ScheduleType
from app.modules.schedules.models import Schedule, ScheduleRun, ScheduleShop
from app.modules.schedules.schemas import ScheduleCreate
from app.modules.schedules.service import ScheduleService
from app.modules.tasks.enums import TaskSkillId, TaskStatus
from app.modules.tasks.exceptions import TaskNotFoundError
from app.modules.tasks.models import Task, TaskEvent
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workers.models import DeviceRuntime, DeviceSkillCapability


pytestmark = pytest.mark.integration


FEATURE_DATABASE = "control_center_feat_device_task_human_access"


@pytest.fixture(scope="session")
def feature_postgresql_engine() -> Engine:
    database_url = get_settings().database_url
    assert database_url is not None
    url = make_url(str(database_url))
    assert url.drivername.startswith("postgresql")
    assert url.database == FEATURE_DATABASE

    engine = get_database_engine()
    assert engine.url == url
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == FEATURE_DATABASE
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "20260905_0029"
        )
    return engine


def _actor(
    *,
    user_id: UUID,
    team_id: UUID,
    scope: DataScope,
) -> ActorContext:
    return ActorContext(
        user_id=user_id,
        user_display_name=f"Device Task Access {scope.value}",
        team_id=team_id,
        membership_id=uuid4(),
        role_code="member",
        data_scope=scope,
    )


def _schedule(
    *,
    schedule_id: UUID,
    team_id: UUID,
    created_by_user_id: UUID | None,
    device_id: UUID,
    now: datetime,
) -> Schedule:
    return Schedule(
        schedule_id=schedule_id,
        team_id=team_id,
        created_by_user_id=created_by_user_id,
        name=f"stage-2a1-access-{schedule_id}",
        enabled=False,
        target_device_id=device_id,
        skill_id=TaskSkillId.SYSTEM_ECHO.value,
        execution_display_name="Echo",
        schedule_type=ScheduleType.DAILY.value,
        local_time=time(9, 0),
        timezone="Asia/Shanghai",
        task_input_json={"message": "scheduled"},
        next_run_at=None,
        created_at=now,
        updated_at=now,
    )


def _task(
    *,
    task_id: UUID,
    team_id: UUID,
    created_by_user_id: UUID | None,
    device_id: UUID,
    now: datetime,
) -> Task:
    return Task(
        task_id=task_id,
        team_id=team_id,
        created_by_user_id=created_by_user_id,
        target_device_id=device_id,
        skill_id=TaskSkillId.SYSTEM_ECHO.value,
        execution_display_name="Echo",
        status=TaskStatus.SUCCESS.value,
        input_json={"message": "legacy"},
        started_at=now - timedelta(minutes=1),
        finished_at=now,
        created_at=now,
        updated_at=now,
    )


def test_postgresql_device_schedule_task_ownership_and_scope(
    feature_postgresql_engine: Engine,
) -> None:
    inspector = inspect(feature_postgresql_engine)
    resource_columns = {
        table_name: {
            column["name"]: column
            for column in inspector.get_columns(table_name)
        }
        for table_name in ("devices", "schedules", "tasks")
    }
    for table_name, columns in resource_columns.items():
        assert columns["team_id"]["nullable"] is False, table_name
        assert columns["created_by_user_id"]["nullable"] is True, table_name

    for table_name, primary_key in (
        ("devices", "device"),
        ("schedules", "schedule"),
        ("tasks", "task"),
    ):
        foreign_keys = {
            key["name"]: key for key in inspector.get_foreign_keys(table_name)
        }
        assert foreign_keys[f"fk_{table_name}_team_id_teams"]["referred_table"] == "teams"
        assert (
            foreign_keys[f"fk_{table_name}_created_by_user_id_users"][
                "referred_table"
            ]
            == "users"
        )
        index_names = {index["name"] for index in inspector.get_indexes(table_name)}
        assert f"ix_{table_name}_team_created_{primary_key}" in index_names
        assert f"ix_{table_name}_team_creator_created_{primary_key}" in index_names

    now = datetime.now(UTC)
    team_a_id, team_b_id = uuid4(), uuid4()
    user_a1_id, user_a2_id, user_b_id, all_user_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    device_ids: set[UUID] = set()
    schedule_ids: set[UUID] = set()
    task_ids: set[UUID] = set()

    try:
        with Session(feature_postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    User(user_id=user_a1_id, display_name="stage-2a1-access-a1"),
                    User(user_id=user_a2_id, display_name="stage-2a1-access-a2"),
                    User(user_id=user_b_id, display_name="stage-2a1-access-b"),
                    User(user_id=all_user_id, display_name="stage-2a1-access-all"),
                ],
            )
            from app.modules.access.models import Team

            session.add_all(
                [
                    Team(team_id=team_a_id, name=f"stage-2a1-access-a-{team_a_id}"),
                    Team(team_id=team_b_id, name=f"stage-2a1-access-b-{team_b_id}"),
                ],
            )
            session.commit()

            self_actor = _actor(
                user_id=user_a1_id,
                team_id=team_a_id,
                scope=DataScope.SELF,
            )
            team_actor = _actor(
                user_id=user_a1_id,
                team_id=team_a_id,
                scope=DataScope.TEAM,
            )
            all_actor = _actor(
                user_id=all_user_id,
                team_id=team_a_id,
                scope=DataScope.ALL,
            )
            team_b_actor = _actor(
                user_id=user_b_id,
                team_id=team_b_id,
                scope=DataScope.TEAM,
            )
            second_team_actor = _actor(
                user_id=user_a2_id,
                team_id=team_a_id,
                scope=DataScope.TEAM,
            )

            device_service = DeviceService(session)
            device_a1 = device_service.create(
                self_actor,
                DeviceCreate(display_name="stage-2a1-access-device-a1"),
            )
            device_a2 = device_service.create(
                second_team_actor,
                DeviceCreate(display_name="stage-2a1-access-device-a2"),
            )
            device_b = device_service.create(
                team_b_actor,
                DeviceCreate(display_name="stage-2a1-access-device-b"),
            )
            device_ids.update(
                {device_a1.device_id, device_a2.device_id, device_b.device_id},
            )
            assert (device_a1.team_id, device_a1.created_by_user_id) == (
                team_a_id,
                user_a1_id,
            )

            self_devices, self_total = device_service.list(
                actor=self_actor,
                offset=0,
                limit=20,
            )
            team_devices, team_total = device_service.list(
                actor=team_actor,
                offset=0,
                limit=20,
            )
            all_devices, all_total = device_service.list(
                actor=all_actor,
                offset=0,
                limit=20,
            )
            assert {device.device_id for device in self_devices} == {device_a1.device_id}
            assert self_total == 1
            assert {device.device_id for device in team_devices} == {
                device_a1.device_id,
                device_a2.device_id,
            }
            assert team_total == 2
            assert {device.device_id for device in all_devices} == device_ids
            assert all_total == 3
            with pytest.raises(DeviceNotFoundError):
                device_service.get(team_actor, device_b.device_id)
            with pytest.raises(DeviceNotFoundError):
                device_service.update(
                    all_actor,
                    device_b.device_id,
                    DeviceUpdate(note="cross-team"),
                )
            session.rollback()

            session.add_all(
                [
                    DeviceRuntime(
                        device_id=device_a1.device_id,
                        worker_version="test",
                        connection_status="online",
                        last_seen_at=now,
                        started_at=now,
                    ),
                    DeviceSkillCapability(
                        device_id=device_a1.device_id,
                        skill_id=TaskSkillId.SYSTEM_ECHO.value,
                        display_name="Echo",
                        runtime="python",
                        provider_code=None,
                        skill_version="1",
                        classification="internal",
                        input_schema=None,
                    ),
                ],
            )
            session.commit()

            schedule_service = ScheduleService(session)
            schedule_read = schedule_service.create(
                ScheduleCreate(
                    name="stage-2a1-access-schedule-a1",
                    target_device_id=device_a1.device_id,
                    execution_type=ScheduleExecutionType.BUSINESS_SKILL,
                    skill_id=TaskSkillId.SYSTEM_ECHO.value,
                    parameters={"message": "scheduled"},
                    schedule_type=ScheduleType.DAILY,
                    local_time=time(9, 0),
                    timezone="Asia/Shanghai",
                ),
                self_actor,
                now=now,
            )
            schedule_ids.add(schedule_read.schedule_id)
            schedule_a1 = session.get(Schedule, schedule_read.schedule_id)
            assert schedule_a1 is not None
            assert (schedule_a1.team_id, schedule_a1.created_by_user_id) == (
                team_a_id,
                user_a1_id,
            )
            schedule_a2 = _schedule(
                schedule_id=uuid4(),
                team_id=team_a_id,
                created_by_user_id=user_a2_id,
                device_id=device_a2.device_id,
                now=now,
            )
            schedule_b = _schedule(
                schedule_id=uuid4(),
                team_id=team_b_id,
                created_by_user_id=user_b_id,
                device_id=device_b.device_id,
                now=now,
            )
            session.add_all([schedule_a2, schedule_b])
            schedule_ids.update({schedule_a2.schedule_id, schedule_b.schedule_id})
            session.commit()

            assert schedule_service.list_management(
                actor=self_actor,
                page=1,
                page_size=20,
                enabled=None,
                device_id=None,
                search=None,
            ).total == 1
            assert schedule_service.list_management(
                actor=team_actor,
                page=1,
                page_size=20,
                enabled=None,
                device_id=None,
                search=None,
            ).total == 2
            assert schedule_service.list_management(
                actor=all_actor,
                page=1,
                page_size=20,
                enabled=None,
                device_id=None,
                search=None,
            ).total == 3

            schedule_a1.next_run_at = now - timedelta(seconds=1)
            session.commit()
            triggered = schedule_service.trigger_next_due(now=now)
            assert triggered is not None and triggered.task_id is not None
            task_ids.add(triggered.task_id)
            scheduled_task = session.get(Task, triggered.task_id)
            assert scheduled_task is not None
            assert (scheduled_task.team_id, scheduled_task.created_by_user_id) == (
                schedule_a1.team_id,
                schedule_a1.created_by_user_id,
            )

            direct_task = TaskService(session).create(
                TaskCreate(
                    target_device_id=device_a1.device_id,
                    skill_id=TaskSkillId.SYSTEM_ECHO.value,
                    input={"message": "direct"},
                ),
                self_actor,
            )
            task_ids.add(direct_task.task_id)
            assert (direct_task.team_id, direct_task.created_by_user_id) == (
                team_a_id,
                user_a1_id,
            )
            task_a2 = _task(
                task_id=uuid4(),
                team_id=team_a_id,
                created_by_user_id=user_a2_id,
                device_id=device_a2.device_id,
                now=now,
            )
            task_b = _task(
                task_id=uuid4(),
                team_id=team_b_id,
                created_by_user_id=user_b_id,
                device_id=device_b.device_id,
                now=now,
            )
            session.add_all(
                [
                    task_a2,
                    task_b,
                    TaskEvent(
                        task_id=task_b.task_id,
                        seq=1,
                        event_type="log",
                        level="info",
                        message="cross-team runtime event",
                        event_at=now,
                        metadata_json={},
                    ),
                ],
            )
            task_ids.update({task_a2.task_id, task_b.task_id})
            session.commit()

            task_service = TaskService(session)
            assert task_service.list_management_tasks(
                actor=self_actor,
                page=1,
                page_size=20,
                status=None,
                device_id=None,
                search=None,
            ).total == 2
            assert task_service.list_management_tasks(
                actor=team_actor,
                page=1,
                page_size=20,
                status=None,
                device_id=None,
                search=None,
            ).total == 3
            assert task_service.list_management_tasks(
                actor=all_actor,
                page=1,
                page_size=20,
                status=None,
                device_id=None,
                search=None,
            ).total == 4
            with pytest.raises(TaskNotFoundError):
                task_service.list_events(
                    team_actor,
                    task_b.task_id,
                    after_seq=None,
                    limit=20,
                )
    finally:
        with Session(feature_postgresql_engine) as session:
            if task_ids:
                session.execute(delete(TaskEvent).where(TaskEvent.task_id.in_(task_ids)))
            if schedule_ids:
                session.execute(
                    delete(ScheduleRun).where(ScheduleRun.schedule_id.in_(schedule_ids)),
                )
                session.execute(
                    delete(ScheduleShop).where(
                        ScheduleShop.schedule_id.in_(schedule_ids),
                    ),
                )
            if task_ids:
                session.execute(delete(Task).where(Task.task_id.in_(task_ids)))
            if schedule_ids:
                session.execute(delete(Schedule).where(Schedule.schedule_id.in_(schedule_ids)))
            if device_ids:
                session.execute(
                    delete(DeviceSkillCapability).where(
                        DeviceSkillCapability.device_id.in_(device_ids),
                    ),
                )
                session.execute(
                    delete(DeviceRuntime).where(DeviceRuntime.device_id.in_(device_ids)),
                )
                session.execute(delete(Device).where(Device.device_id.in_(device_ids)))
            session.execute(
                delete(User).where(
                    User.user_id.in_({user_a1_id, user_a2_id, user_b_id, all_user_id}),
                ),
            )
            from app.modules.access.models import Team

            session.execute(delete(Team).where(Team.team_id.in_({team_a_id, team_b_id})))
            session.commit()
