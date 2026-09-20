from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Engine, delete, event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.models import Team, TeamDeviceAccess
from app.modules.automation_apps.models import AutomationApplicationConfig
from app.modules.devices.models import Device
from app.modules.schedules.models import Schedule, ScheduleRun, ScheduleShop
from app.modules.schedules.enums import ScheduleExecutionType
from app.modules.schedules.exceptions import ScheduleNotFoundError
from app.modules.schedules.repository import ScheduleRepository
from app.modules.schedules.schemas import ScheduleCreate, ScheduleUpdate
from app.modules.schedules.service import ScheduleService
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.tasks.models import Task, TaskEvent
from app.modules.tasks.schemas import TaskComplete, TaskEventBatchWrite, TaskFail
from app.modules.tasks.service import PreparedTaskCreation, TaskService
from app.modules.users.models import User
from app.modules.workers.models import (
    DeviceProviderInventory,
    DeviceSkillCapability,
)
from app.modules.workers.service import WorkerPrincipal


pytestmark = pytest.mark.integration


class _PreparedTaskService:
    def prepare_scheduled_task(
        self,
        data: object,
        *,
        team_id: UUID,
        actor: object | None = None,
    ) -> PreparedTaskCreation:
        del data, team_id, actor
        return PreparedTaskCreation(
            input_json={"message": "safe"},
            execution_display_name="系统回声验证",
        )


def _ready_inventory(now: datetime) -> dict[str, object]:
    return {
        "provider": "yingdao",
        "available": True,
        "status": "ready",
        "status_reason_code": None,
        "status_reason": None,
        "provider_version": "6.3.6",
        "execution_available": True,
        "execution_version": "6.3.6",
        "execution_unavailable_reason": None,
        "logged_in": True,
        "account_display": "Scheduler Fixture",
        "account_type": "PersonalBasic",
        "enterprise_account": False,
        "user_id": "900000000000000001",
        "applications": [
            {
                "app_id": "scheduler-safe-app",
                "app_name": "Scheduler Safe App",
                "version_id": "1",
                "updated_at": None,
                "app_type": None,
                "group_id": None,
            },
        ],
        "discovered_at": now.isoformat(),
    }


def _fixture_actor() -> tuple[UUID, UUID, ActorContext]:
    team_id = uuid4()
    user_id = uuid4()
    return team_id, user_id, ActorContext(
        user_id=user_id,
        user_display_name="Scheduler Integration User",
        team_id=team_id,
        membership_id=uuid4(),
        role_code="member",
        data_scope=DataScope.TEAM,
    )


def _cleanup(
    engine: Engine,
    device_id: UUID,
    *,
    team_id: UUID,
    user_id: UUID,
) -> None:
    with Session(engine) as session:
        schedule_ids = list(
            session.scalars(
                select(Schedule.schedule_id).where(
                    Schedule.target_device_id == device_id,
                ),
            ),
        )
        if schedule_ids:
            session.execute(
                delete(ScheduleRun).where(
                    ScheduleRun.schedule_id.in_(schedule_ids),
                ),
            )
            session.execute(
                delete(Schedule).where(Schedule.schedule_id.in_(schedule_ids)),
            )
        task_ids = select(Task.task_id).where(Task.target_device_id == device_id)
        session.execute(delete(TaskEvent).where(TaskEvent.task_id.in_(task_ids)))
        session.execute(delete(Task).where(Task.target_device_id == device_id))
        session.execute(
            delete(DeviceProviderInventory).where(
                DeviceProviderInventory.device_id == device_id,
            ),
        )
        session.execute(
            delete(DeviceSkillCapability).where(
                DeviceSkillCapability.device_id == device_id,
            ),
        )
        session.execute(
            delete(AutomationApplicationConfig).where(
                AutomationApplicationConfig.provider_code == "yingdao",
                AutomationApplicationConfig.app_id == "scheduler-safe-app",
            ),
        )
        session.execute(
            delete(TeamDeviceAccess).where(TeamDeviceAccess.team_id == team_id),
        )
        session.execute(delete(Device).where(Device.device_id == device_id))
        session.execute(delete(User).where(User.user_id == user_id))
        session.execute(delete(Team).where(Team.team_id == team_id))
        session.commit()


def test_schedule_shop_set_can_be_replaced_and_reordered(
    postgresql_engine: Engine,
) -> None:
    device_id = uuid4()
    team_id, user_id, actor = _fixture_actor()
    schedule_id = uuid4()
    shop_ids = [uuid4(), uuid4(), uuid4()]
    now = datetime.now(UTC)
    try:
        with Session(postgresql_engine) as session:
            session.add_all(
                [
                    Team(team_id=team_id, name="Scheduler Shop Set Team"),
                    User(
                        user_id=user_id,
                        display_name="Scheduler Shop Set User",
                    ),
                    Device(
                        device_id=device_id,
                        team_id=team_id,
                        display_name="多店铺计划设备",
                    ),
                ],
            )
            session.add_all(
                [
                    Shop(
                        shop_id=shop_id,
                        display_name=f"多店铺计划店铺 {position}",
                        platform=ShopPlatform.DOUYIN,
                    )
                    for position, shop_id in enumerate(shop_ids, start=1)
                ],
            )
            session.flush()
            session.add(TeamDeviceAccess(team_id=team_id, device_id=device_id))
            session.add(
                Schedule(
                    schedule_id=schedule_id,
                    team_id=team_id,
                    name="多店铺顺序计划",
                    enabled=True,
                    target_device_id=device_id,
                    shop_links=[
                        ScheduleShop(shop_id=shop_ids[0], position=0),
                        ScheduleShop(shop_id=shop_ids[1], position=1),
                    ],
                    skill_id="system.echo",
                    execution_display_name="系统回声验证",
                    schedule_type="daily",
                    local_time=time(9, 30),
                    timezone="Asia/Shanghai",
                    task_input_json={"message": "safe"},
                    next_run_at=now + timedelta(days=1),
                ),
            )
            session.commit()

        with Session(postgresql_engine) as session:
            updated = ScheduleService(
                session,
                task_service=_PreparedTaskService(),  # type: ignore[arg-type]
            ).update(
                schedule_id,
                ScheduleUpdate(shop_ids=[shop_ids[1], shop_ids[2]]),
                actor,
                now=now,
            )
            assert updated.shop_ids == [shop_ids[1], shop_ids[2]]

        with Session(postgresql_engine) as session:
            schedule = session.get(Schedule, schedule_id)
            assert schedule is not None
            assert schedule.shop_ids == [shop_ids[1], shop_ids[2]]
    finally:
        with Session(postgresql_engine) as session:
            session.execute(
                delete(ScheduleShop).where(ScheduleShop.schedule_id == schedule_id),
            )
            session.execute(
                delete(Schedule).where(Schedule.schedule_id == schedule_id),
            )
            session.execute(
                delete(TeamDeviceAccess).where(
                    TeamDeviceAccess.team_id == team_id,
                ),
            )
            session.execute(delete(Shop).where(Shop.shop_id.in_(shop_ids)))
            session.execute(delete(Device).where(Device.device_id == device_id))
            session.execute(delete(User).where(User.user_id == user_id))
            session.execute(delete(Team).where(Team.team_id == team_id))
            session.commit()


def test_scheduler_coalesces_is_idempotent_and_keeps_list_query_bounded(
    postgresql_engine: Engine,
) -> None:
    device_id = uuid4()
    team_id, user_id, actor = _fixture_actor()
    schedule_id: UUID | None = None
    now = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    try:
        with Session(postgresql_engine) as session:
            session.add_all(
                [
                    Team(team_id=team_id, name="Scheduler Daily Team"),
                    User(user_id=user_id, display_name="Scheduler Daily User"),
                    Device(
                        device_id=device_id,
                        team_id=team_id,
                        display_name="Scheduler 设备",
                    ),
                ],
            )
            session.add(
                DeviceSkillCapability(
                    device_id=device_id,
                    skill_id="yingdao.app.run",
                    display_name="运行影刀应用",
                    runtime="rpa",
                    provider_code="yingdao",
                    skill_version="1",
                    classification="internal",
                ),
            )
            inventory = _ready_inventory(now)
            session.add(
                DeviceProviderInventory(
                    device_id=device_id,
                    provider_code="yingdao",
                    available=True,
                    provider_version="6.3.6",
                    account_display="Scheduler Fixture",
                    account_type="PersonalBasic",
                    enterprise_account=False,
                    last_discovered_at=now,
                    inventory_payload=inventory,
                ),
            )
            session.add(
                AutomationApplicationConfig(
                    provider_code="yingdao",
                    app_id="scheduler-safe-app",
                    schema_source="manual",
                    input_schema={
                        "fields": [
                            {
                                "name": "keyword",
                                "label": "关键词",
                                "type": "text",
                                "required": True,
                                "default_value": None,
                                "options": [],
                            },
                        ],
                    },
                    default_values={},
                    version=1,
                ),
            )
            session.flush()
            session.add(TeamDeviceAccess(team_id=team_id, device_id=device_id))
            session.commit()

        with Session(postgresql_engine) as session:
            created = ScheduleService(session).create(
                ScheduleCreate(
                    name="每日安全计划",
                    target_device_id=device_id,
                    application_id="scheduler-safe-app",
                    parameters={"keyword": "safe"},
                    local_time=time(9, 30),
                    timezone="Asia/Shanghai",
                ),
                actor,
                now=now,
            )
            schedule_id = created.schedule_id
            disabled = ScheduleService(session).update(
                schedule_id,
                ScheduleUpdate(enabled=False),
                actor,
                now=now,
            )
            assert disabled.enabled is False
            assert disabled.next_run_at is None
            edited = ScheduleService(session).update(
                schedule_id,
                ScheduleUpdate(
                    name="每日安全计划（已编辑）",
                    local_time=time(10, 15),
                    timezone="Asia/Tokyo",
                    enabled=True,
                ),
                actor,
                now=now,
            )
            assert edited.name == "每日安全计划（已编辑）"
            assert edited.timezone == "Asia/Tokyo"
            assert edited.next_run_at == datetime(
                2026,
                8,
                25,
                1,
                15,
                tzinfo=UTC,
            )
            restored = ScheduleService(session).update(
                schedule_id,
                ScheduleUpdate(
                    local_time=time(9, 30),
                    timezone="Asia/Shanghai",
                ),
                actor,
                now=now,
            )
            assert restored.next_run_at == datetime(
                2026,
                8,
                25,
                1,
                30,
                tzinfo=UTC,
            )
            schedule = session.get(Schedule, schedule_id)
            assert schedule is not None
            schedule.next_run_at = now - timedelta(days=4)
            session.commit()

        first_session = Session(postgresql_engine)
        second_session = Session(postgresql_engine)
        try:
            locked = ScheduleRepository(first_session).get_next_due(now=now)
            skipped = ScheduleRepository(second_session).get_next_due(now=now)
            assert locked is not None
            assert skipped is None
        finally:
            first_session.rollback()
            second_session.rollback()
            first_session.close()
            second_session.close()

        with Session(postgresql_engine) as session:
            triggered = ScheduleService(session).trigger_next_due(now=now)
        assert triggered is not None
        assert triggered.scheduled_for == datetime(
            2026,
            8,
            24,
            1,
            30,
            tzinfo=UTC,
        )
        assert triggered.task_id is not None

        with Session(postgresql_engine) as session:
            task = session.get(Task, triggered.task_id)
            run = session.get(ScheduleRun, triggered.run_id)
            schedule = session.get(Schedule, schedule_id)
            assert task is not None and task.status == "pending"
            assert task.execution_display_name == "Scheduler Safe App"
            assert task.input_json == {
                "app_id": "scheduler-safe-app",
                "params": {"keyword": "safe"},
            }
            assert run is not None and run.task_id == task.task_id
            assert schedule is not None
            assert schedule.next_run_at == datetime(
                2026,
                8,
                25,
                1,
                30,
                tzinfo=UTC,
            )
            assert ScheduleService(session).trigger_next_due(now=now) is None

        with Session(postgresql_engine) as session:
            session.add(
                ScheduleRun(
                    schedule_id=schedule_id,
                    scheduled_for=triggered.scheduled_for,
                    trigger_result="blocked",
                ),
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
            runs = list(
                session.scalars(
                    select(ScheduleRun).where(
                        ScheduleRun.schedule_id == schedule_id,
                        ScheduleRun.scheduled_for == triggered.scheduled_for,
                    ),
                ),
            )
            assert [run.run_id for run in runs] == [triggered.run_id]

        statements: list[str] = []

        def record_statement(
            connection: object,
            cursor: object,
            statement: str,
            parameters: object,
            context: object,
            executemany: bool,
        ) -> None:
            del connection, cursor, parameters, context, executemany
            statements.append(statement)

        event.listen(postgresql_engine, "before_cursor_execute", record_statement)
        try:
            with Session(postgresql_engine) as session:
                page = ScheduleService(session).list_management(
                    actor=actor,
                    page=1,
                    page_size=20,
                    enabled=None,
                    device_id=device_id,
                    search=None,
                )
            assert page.total == 1
            assert page.items[0].latest_run is not None
            assert page.items[0].latest_run.task_status is not None
            # Count + page summary + one bounded select-in query for ordered shops.
            assert len(statements) == 3
        finally:
            event.remove(
                postgresql_engine,
                "before_cursor_execute",
                record_statement,
            )

        with postgresql_engine.connect() as connection:
            connection.execute(text("SET LOCAL enable_seqscan = off"))
            plan = "\n".join(
                row[0]
                for row in connection.execute(
                    text(
                        "EXPLAIN SELECT schedule_id FROM schedules "
                        "WHERE enabled IS TRUE AND deleted_at IS NULL "
                        "AND next_run_at IS NOT NULL AND next_run_at <= :now "
                        "ORDER BY next_run_at ASC, schedule_id ASC LIMIT 1"
                    ),
                    {"now": now},
                )
            )
            assert "ix_schedules_due" in plan

        blocked_at = now + timedelta(days=1)
        with Session(postgresql_engine) as session:
            device = session.get(Device, device_id)
            schedule = session.get(Schedule, schedule_id)
            assert device is not None and schedule is not None
            device.enabled = False
            schedule.next_run_at = blocked_at - timedelta(minutes=1)
            session.commit()
        with Session(postgresql_engine) as session:
            blocked = ScheduleService(session).trigger_next_due(now=blocked_at)
        assert blocked is not None
        assert blocked.task_id is None
        with Session(postgresql_engine) as session:
            blocked_run = session.get(ScheduleRun, blocked.run_id)
            assert blocked_run is not None
            assert blocked_run.trigger_result == "blocked"
            assert blocked_run.trigger_error_code == "TASK_DEVICE_DISABLED"

        deleted_at = blocked_at + timedelta(days=1)
        with Session(postgresql_engine) as session:
            device = session.get(Device, device_id)
            schedule = session.get(Schedule, schedule_id)
            assert device is not None and schedule is not None
            device.enabled = True
            device.deleted_at = deleted_at
            schedule.next_run_at = deleted_at - timedelta(minutes=1)
            session.commit()
        with Session(postgresql_engine) as session:
            deleted_target = ScheduleService(session).trigger_next_due(now=deleted_at)
        assert deleted_target is not None
        assert deleted_target.task_id is None
        with Session(postgresql_engine) as session:
            deleted_run = session.get(ScheduleRun, deleted_target.run_id)
            assert deleted_run is not None
            assert deleted_run.trigger_error_code == "TASK_TARGET_DEVICE_INVALID"

        application_changed_at = deleted_at + timedelta(days=1)
        with Session(postgresql_engine) as session:
            device = session.get(Device, device_id)
            schedule = session.get(Schedule, schedule_id)
            inventory = session.get(DeviceProviderInventory, (device_id, "yingdao"))
            assert device is not None and schedule is not None and inventory is not None
            device.deleted_at = None
            schedule.next_run_at = application_changed_at - timedelta(minutes=1)
            changed_inventory = dict(inventory.inventory_payload)
            changed_inventory["applications"] = []
            inventory.inventory_payload = changed_inventory
            session.commit()
        with Session(postgresql_engine) as session:
            application_missing = ScheduleService(session).trigger_next_due(
                now=application_changed_at,
            )
        assert application_missing is not None
        assert application_missing.task_id is None
        with Session(postgresql_engine) as session:
            missing_run = session.get(ScheduleRun, application_missing.run_id)
            assert missing_run is not None
            assert missing_run.trigger_error_code == "TASK_APPLICATION_NOT_AVAILABLE"

        params_changed_at = application_changed_at + timedelta(days=1)
        with Session(postgresql_engine) as session:
            schedule = session.get(Schedule, schedule_id)
            inventory = session.get(DeviceProviderInventory, (device_id, "yingdao"))
            config = session.scalar(
                select(AutomationApplicationConfig).where(
                    AutomationApplicationConfig.provider_code == "yingdao",
                    AutomationApplicationConfig.app_id == "scheduler-safe-app",
                ),
            )
            assert schedule is not None and inventory is not None and config is not None
            inventory.inventory_payload = _ready_inventory(params_changed_at)
            config.input_schema = {
                "fields": [
                    {
                        "name": "new_required_value",
                        "label": "新必填参数",
                        "type": "text",
                        "required": True,
                        "default_value": None,
                        "options": [],
                    },
                ],
            }
            schedule.next_run_at = params_changed_at - timedelta(minutes=1)
            session.commit()
        with Session(postgresql_engine) as session:
            params_invalid = ScheduleService(session).trigger_next_due(
                now=params_changed_at,
            )
        assert params_invalid is not None
        assert params_invalid.task_id is None
        with Session(postgresql_engine) as session:
            invalid_run = session.get(ScheduleRun, params_invalid.run_id)
            assert invalid_run is not None
            assert invalid_run.trigger_error_code == "TASK_INPUT_INVALID"
    finally:
        _cleanup(
            postgresql_engine,
            device_id,
            team_id=team_id,
            user_id=user_id,
        )


def test_occurrence_date_filter_uses_runs_or_next_run_in_the_selected_timezone(
    postgresql_engine: Engine,
) -> None:
    device_id = uuid4()
    team_id, user_id, actor = _fixture_actor()
    selected_date = datetime(2026, 8, 25, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    selected_occurrence = selected_date.astimezone(UTC) + timedelta(hours=1)
    next_day_occurrence = selected_occurrence + timedelta(days=1)
    once_id = uuid4()
    weekly_id = uuid4()
    disabled_id = uuid4()
    outside_id = uuid4()
    try:
        with Session(postgresql_engine) as session:
            session.add_all(
                [
                    Team(team_id=team_id, name="Schedule Date Filter Team"),
                    User(user_id=user_id, display_name="Schedule Date Filter User"),
                    Device(
                        device_id=device_id,
                        team_id=team_id,
                        display_name="Schedule Date Filter Device",
                    ),
                    Schedule(
                        schedule_id=once_id,
                        team_id=team_id,
                        name="One-time selected date",
                        enabled=True,
                        target_device_id=device_id,
                        skill_id="system.echo",
                        execution_display_name="System Echo",
                        schedule_type="once",
                        local_time=time(9, 0),
                        timezone="Asia/Shanghai",
                        local_date=selected_date.date(),
                        weekdays=[],
                        task_input_json={"message": "once"},
                        next_run_at=selected_occurrence,
                    ),
                    Schedule(
                        schedule_id=weekly_id,
                        team_id=team_id,
                        name="Weekly selected date",
                        enabled=True,
                        target_device_id=device_id,
                        skill_id="system.echo",
                        execution_display_name="System Echo",
                        schedule_type="weekly",
                        local_time=time(9, 0),
                        timezone="Asia/Shanghai",
                        local_date=None,
                        weekdays=[2],
                        task_input_json={"message": "weekly"},
                        next_run_at=selected_occurrence,
                    ),
                    Schedule(
                        schedule_id=disabled_id,
                        team_id=team_id,
                        name="Disabled schedule with selected run",
                        enabled=False,
                        target_device_id=device_id,
                        skill_id="system.echo",
                        execution_display_name="System Echo",
                        schedule_type="daily",
                        local_time=time(9, 0),
                        timezone="Asia/Shanghai",
                        local_date=None,
                        weekdays=[],
                        task_input_json={"message": "disabled"},
                        next_run_at=None,
                    ),
                    Schedule(
                        schedule_id=outside_id,
                        team_id=team_id,
                        name="Outside selected date",
                        enabled=True,
                        target_device_id=device_id,
                        skill_id="system.echo",
                        execution_display_name="System Echo",
                        schedule_type="daily",
                        local_time=time(9, 0),
                        timezone="Asia/Shanghai",
                        local_date=None,
                        weekdays=[],
                        task_input_json={"message": "outside"},
                        next_run_at=next_day_occurrence,
                    ),
                    ScheduleRun(
                        schedule_id=disabled_id,
                        scheduled_for=selected_occurrence,
                        trigger_result="blocked",
                    ),
                ],
            )
            session.flush()
            session.add(TeamDeviceAccess(team_id=team_id, device_id=device_id))
            session.commit()

        with Session(postgresql_engine) as session:
            page = ScheduleService(session).list_management(
                actor=actor,
                page=1,
                page_size=20,
                enabled=None,
                device_id=device_id,
                search=None,
                occurrence_date=selected_date.date(),
                view_timezone="Asia/Shanghai",
            )

        assert page.total == 3
        assert {item.schedule_id for item in page.items} == {
            once_id,
            weekly_id,
            disabled_id,
        }
        by_id = {item.schedule_id: item for item in page.items}
        assert by_id[once_id].local_date == selected_date.date()
        assert by_id[weekly_id].weekdays == [2]
        assert by_id[disabled_id].enabled is False
        assert by_id[disabled_id].latest_run is not None
        assert by_id[disabled_id].latest_run.scheduled_for == selected_occurrence
    finally:
        _cleanup(
            postgresql_engine,
            device_id,
            team_id=team_id,
            user_id=user_id,
        )


def test_scheduler_created_task_uses_existing_worker_runtime_lifecycle(
    postgresql_engine: Engine,
) -> None:
    """Exercise a safe internal Task through the ordinary claim/event/complete path."""

    device_id = uuid4()
    team_id, user_id, actor = _fixture_actor()
    now = datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(minutes=5)
    local_time = (
        now.astimezone(ZoneInfo("Asia/Shanghai")).time().replace(tzinfo=None)
    )
    try:
        with Session(postgresql_engine) as session:
            session.add_all(
                [
                    Team(team_id=team_id, name="Scheduler Runtime Team"),
                    User(user_id=user_id, display_name="Scheduler Runtime User"),
                    Device(
                        device_id=device_id,
                        team_id=team_id,
                        display_name="Scheduler E2E 设备",
                    ),
                ],
            )
            session.add(
                DeviceSkillCapability(
                    device_id=device_id,
                    skill_id="system.echo",
                    display_name="系统回声验证",
                    runtime="python",
                    provider_code=None,
                    skill_version="1",
                    classification="internal",
                ),
            )
            session.add(
                Schedule(
                    team_id=team_id,
                    name="Scheduler 安全闭环",
                    enabled=True,
                    target_device_id=device_id,
                    skill_id="system.echo",
                    execution_display_name="系统回声验证",
                    schedule_type="daily",
                    local_time=local_time,
                    timezone="Asia/Shanghai",
                    task_input_json={"message": "scheduler-safe-e2e"},
                    next_run_at=now,
                ),
            )
            session.flush()
            session.add(TeamDeviceAccess(team_id=team_id, device_id=device_id))
            session.commit()

        with Session(postgresql_engine) as session:
            triggered = ScheduleService(session).trigger_next_due(now=now)
        assert triggered is not None
        assert triggered.task_id is not None
        task_id = triggered.task_id

        principal = WorkerPrincipal(device_id=device_id)
        with Session(postgresql_engine) as session:
            claimed = TaskService(session).claim(principal, now=now)
            assert claimed is not None
            assert claimed.task_id == task_id
            assert claimed.status == "running"

        with Session(postgresql_engine) as session:
            accepted = TaskService(session).append_events(
                principal,
                task_id,
                TaskEventBatchWrite.model_validate(
                    {
                        "events": [
                            {
                                "seq": 1,
                                "event_type": "log",
                                "level": "info",
                                "message": "scheduler-safe-e2e",
                                "event_at": now + timedelta(seconds=1),
                                "metadata": {},
                            },
                        ],
                    },
                ),
                now=now + timedelta(seconds=1),
            )
            assert accepted.accepted_count == 1

        with Session(postgresql_engine) as session:
            completed = TaskService(session).complete(
                principal,
                task_id,
                TaskComplete(result={"echo": "scheduler-safe-e2e"}),
                now=now + timedelta(seconds=2),
            )
            assert completed.status == "success"

        with Session(postgresql_engine) as session:
            task = session.get(Task, task_id)
            events = list(
                session.scalars(
                    select(TaskEvent).where(TaskEvent.task_id == task_id),
                ),
            )
            run = session.get(ScheduleRun, triggered.run_id)
            schedule = session.get(Schedule, triggered.schedule_id)
            assert task is not None and task.status == "success"
            assert [event.message for event in events] == ["scheduler-safe-e2e"]
            assert run is not None and run.task_id == task_id
            assert schedule is not None
            assert schedule.next_run_at == now + timedelta(days=1)
            assert ScheduleService(session).trigger_next_due(now=now) is None

        with Session(postgresql_engine) as session:
            service = ScheduleService(session)
            service.archive(
                triggered.schedule_id,
                actor,
                now=now + timedelta(seconds=3),
            )
            history = service.list_runs(
                triggered.schedule_id,
                actor,
                page=1,
                page_size=20,
            )
            assert history.total == 1
            assert history.items[0].task_status == "success"
            with pytest.raises(ScheduleNotFoundError):
                service.get(actor, triggered.schedule_id)
    finally:
        _cleanup(
            postgresql_engine,
            device_id,
            team_id=team_id,
            user_id=user_id,
        )


def test_business_skill_schedule_validates_current_contract_and_uses_task_runtime(
    postgresql_engine: Engine,
) -> None:
    device_id = uuid4()
    team_id, user_id, actor = _fixture_actor()
    now = datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(minutes=5)
    schema = {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "title": "关键词",
                "minLength": 1,
            },
            "limit": {
                "type": "integer",
                "title": "数量",
                "default": 10,
                "minimum": 1,
            },
            "dry_run": {
                "type": "boolean",
                "title": "仅验证",
                "default": True,
            },
        },
        "required": ["keyword"],
        "additionalProperties": False,
    }
    try:
        with Session(postgresql_engine) as session:
            session.add_all(
                [
                    Team(team_id=team_id, name="Scheduler Skill Team"),
                    User(user_id=user_id, display_name="Scheduler Skill User"),
                    Device(
                        device_id=device_id,
                        team_id=team_id,
                        display_name="Business Skill 设备",
                    ),
                ],
            )
            session.add(
                DeviceSkillCapability(
                    device_id=device_id,
                    skill_id="catalog.fixture.run",
                    display_name="目录测试能力",
                    runtime="python",
                    provider_code=None,
                    skill_version="1.0.0",
                    classification="business",
                    input_schema=schema,
                ),
            )
            session.flush()
            session.add(TeamDeviceAccess(team_id=team_id, device_id=device_id))
            session.commit()

        with Session(postgresql_engine) as session:
            service = ScheduleService(session)
            created = service.create(
                ScheduleCreate(
                    name="业务 Skill 每日计划",
                    target_device_id=device_id,
                    execution_type=ScheduleExecutionType.BUSINESS_SKILL,
                    skill_id="catalog.fixture.run",
                    parameters={"keyword": "safe"},
                    local_time=time(9, 30),
                    timezone="Asia/Shanghai",
                ),
                actor,
                now=now,
            )
            assert created.execution_type is ScheduleExecutionType.BUSINESS_SKILL
            assert created.application_id is None
            assert created.skill_id == "catalog.fixture.run"
            assert created.execution_display_name == "目录测试能力"
            assert created.parameters == {
                "keyword": "safe",
                "limit": 10,
                "dry_run": True,
            }
            schedule = session.get(Schedule, created.schedule_id)
            assert schedule is not None
            schedule.next_run_at = now
            session.commit()

        with Session(postgresql_engine) as session:
            triggered = ScheduleService(session).trigger_next_due(now=now)
        assert triggered is not None and triggered.task_id is not None
        principal = WorkerPrincipal(device_id=device_id)
        with Session(postgresql_engine) as session:
            claimed = TaskService(session).claim(principal, now=now)
            assert claimed is not None and claimed.task_id == triggered.task_id
            assert claimed.input_json == {
                "keyword": "safe",
                "limit": 10,
                "dry_run": True,
            }
        with Session(postgresql_engine) as session:
            accepted = TaskService(session).append_events(
                principal,
                triggered.task_id,
                TaskEventBatchWrite.model_validate(
                    {
                        "events": [
                            {
                                "seq": 1,
                                "event_type": "log",
                                "level": "info",
                                "message": "开始安全验证",
                                "event_at": now + timedelta(seconds=1),
                                "metadata": {},
                            },
                            {
                                "seq": 2,
                                "event_type": "progress",
                                "level": "info",
                                "message": "已处理 1 项",
                                "event_at": now + timedelta(seconds=2),
                                "metadata": {"current": 1, "total": 1},
                            },
                        ],
                    },
                ),
                now=now + timedelta(seconds=2),
            )
            assert accepted.accepted_count == 2
        with Session(postgresql_engine) as session:
            completed = TaskService(session).complete(
                principal,
                triggered.task_id,
                TaskComplete(result={"summary": "安全验证完成"}),
                now=now + timedelta(seconds=3),
            )
            assert completed.status == "success"

        skill_removed_at = now + timedelta(days=1)
        with Session(postgresql_engine) as session:
            schedule = session.get(Schedule, triggered.schedule_id)
            capability = session.get(
                DeviceSkillCapability,
                (device_id, "catalog.fixture.run"),
            )
            assert schedule is not None and capability is not None
            session.delete(capability)
            schedule.next_run_at = skill_removed_at
            session.commit()
        with Session(postgresql_engine) as session:
            removed = ScheduleService(session).trigger_next_due(now=skill_removed_at)
        assert removed is not None and removed.task_id is None
        with Session(postgresql_engine) as session:
            run = session.get(ScheduleRun, removed.run_id)
            assert run is not None
            assert run.trigger_error_code == "TASK_SKILL_NOT_AVAILABLE"

        schema_changed_at = skill_removed_at + timedelta(days=1)
        with Session(postgresql_engine) as session:
            schedule = session.get(Schedule, triggered.schedule_id)
            assert schedule is not None
            session.add(
                DeviceSkillCapability(
                    device_id=device_id,
                    skill_id="catalog.fixture.run",
                    display_name="目录测试能力 V2",
                    runtime="python",
                    provider_code=None,
                    skill_version="2.0.0",
                    classification="business",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "replacement": {"type": "string"},
                        },
                        "required": ["replacement"],
                        "additionalProperties": False,
                    },
                ),
            )
            schedule.next_run_at = schema_changed_at
            session.commit()
        with Session(postgresql_engine) as session:
            changed = ScheduleService(session).trigger_next_due(now=schema_changed_at)
        assert changed is not None and changed.task_id is None
        with Session(postgresql_engine) as session:
            run = session.get(ScheduleRun, changed.run_id)
            assert run is not None
            assert run.trigger_error_code == "TASK_INPUT_INVALID"
    finally:
        _cleanup(
            postgresql_engine,
            device_id,
            team_id=team_id,
            user_id=user_id,
        )


def test_same_time_schedules_create_tasks_in_stable_order_and_failure_does_not_block(
    postgresql_engine: Engine,
) -> None:
    device_id = uuid4()
    team_id, user_id, _ = _fixture_actor()
    now = datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(minutes=5)
    local_time = (
        now.astimezone(ZoneInfo("Asia/Shanghai")).time().replace(tzinfo=None)
    )
    schedule_ids = [
        UUID("62000000-0000-4000-8000-000000000001"),
        UUID("62000000-0000-4000-8000-000000000002"),
        UUID("62000000-0000-4000-8000-000000000003"),
    ]
    try:
        with Session(postgresql_engine) as session:
            session.add_all(
                [
                    Team(team_id=team_id, name="Scheduler Queue Team"),
                    User(user_id=user_id, display_name="Scheduler Queue User"),
                    Device(
                        device_id=device_id,
                        team_id=team_id,
                        display_name="Scheduler Queue 设备",
                    ),
                ],
            )
            session.add(
                DeviceSkillCapability(
                    device_id=device_id,
                    skill_id="system.echo",
                    display_name="系统回声验证",
                    runtime="python",
                    provider_code=None,
                    skill_version="1",
                    classification="internal",
                ),
            )
            for index, schedule_id in enumerate(reversed(schedule_ids), start=1):
                session.add(
                    Schedule(
                        schedule_id=schedule_id,
                        team_id=team_id,
                        name=f"Queue {index}",
                        enabled=True,
                        target_device_id=device_id,
                        skill_id="system.echo",
                        execution_display_name=f"Queue {index}",
                        schedule_type="daily",
                        local_time=local_time,
                        timezone="Asia/Shanghai",
                        task_input_json={"message": f"queue-{index}"},
                        next_run_at=now,
                    ),
                )
            session.flush()
            session.add(TeamDeviceAccess(team_id=team_id, device_id=device_id))
            session.commit()

        triggered = []
        for _ in schedule_ids:
            with Session(postgresql_engine) as session:
                result = ScheduleService(session).trigger_next_due(now=now)
            assert result is not None
            triggered.append(result)
        assert [item.schedule_id for item in triggered] == schedule_ids

        principal = WorkerPrincipal(device_id=device_id)
        with Session(postgresql_engine) as session:
            first = TaskService(session).claim(principal, now=now)
            assert first is not None
            assert first.task_id == triggered[0].task_id
        with Session(postgresql_engine) as session:
            failed = TaskService(session).fail(
                principal,
                first.task_id,
                TaskFail(error_code="SAFE_TEST_FAILURE", error_message="安全测试失败"),
                now=now + timedelta(seconds=1),
            )
            assert failed.status == "failed"
        with Session(postgresql_engine) as session:
            second = TaskService(session).claim(
                principal,
                now=now + timedelta(seconds=2),
            )
            assert second is not None
            assert second.task_id == triggered[1].task_id
            third = session.get(Task, triggered[2].task_id)
            assert third is not None and third.status == "pending"
    finally:
        _cleanup(
            postgresql_engine,
            device_id,
            team_id=team_id,
            user_id=user_id,
        )
