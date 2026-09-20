from datetime import UTC, datetime, time
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import BaseModel, ConfigDict, SecretStr
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.models import Team, TeamDeviceAccess, TeamShopAccess
from app.core.security import SecretCipher
from app.modules.credentials.models import PlatformCredential, ShopCredentialBinding
from app.modules.credentials.schemas import CredentialCreate
from app.modules.credentials.service import CredentialService
from app.modules.devices.models import Device
from app.modules.schedules.enums import ScheduleExecutionType
from app.modules.schedules.models import Schedule, ScheduleRun, ScheduleShop
from app.modules.schedules.schemas import ScheduleCreate, ScheduleUpdate
from app.modules.schedules.service import ScheduleService
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop, ShopDeviceBinding
from app.modules.tasks.models import Task, TaskEvent, TaskShop
from app.modules.tasks.schemas import TaskComplete, TaskCreate
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workers.models import (
    DeviceProviderInventory,
    DeviceRuntime,
    DeviceSkillCapability,
)
from app.modules.workers.service import WorkerPrincipal


pytestmark = pytest.mark.integration


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
        "account_display": "Task Account Fixture",
        "account_type": "PersonalBasic",
        "enterprise_account": False,
        "user_id": "900000000000000018",
        "applications": [
            {
                "app_id": "task-account-safe-app",
                "app_name": "Task Account Safe App",
                "version_id": "1",
                "updated_at": None,
                "app_type": None,
                "group_id": None,
            },
        ],
        "discovered_at": now.isoformat(),
    }


def _cleanup(
    engine: Engine,
    *,
    device_id: UUID,
    shop_ids: set[UUID],
    credential_ids: set[UUID],
    team_id: UUID,
    user_id: UUID,
) -> None:
    with Session(engine) as session:
        schedule_ids = session.query(Schedule.schedule_id).where(
            Schedule.target_device_id == device_id,
        )
        session.execute(
            delete(ScheduleRun).where(ScheduleRun.schedule_id.in_(schedule_ids)),
        )
        session.execute(
            delete(ScheduleShop).where(ScheduleShop.schedule_id.in_(schedule_ids)),
        )
        session.execute(delete(Schedule).where(Schedule.target_device_id == device_id))
        task_ids = session.query(Task.task_id).where(
            Task.target_device_id == device_id,
        )
        session.execute(delete(TaskEvent).where(TaskEvent.task_id.in_(task_ids)))
        session.execute(delete(TaskShop).where(TaskShop.task_id.in_(task_ids)))
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
        session.execute(delete(DeviceRuntime).where(DeviceRuntime.device_id == device_id))
        session.execute(
            delete(ShopCredentialBinding).where(
                ShopCredentialBinding.shop_id.in_(shop_ids),
            ),
        )
        session.execute(
            delete(ShopDeviceBinding).where(
                ShopDeviceBinding.shop_id.in_(shop_ids),
            ),
        )
        session.execute(
            delete(TeamDeviceAccess).where(TeamDeviceAccess.team_id == team_id),
        )
        session.execute(
            delete(TeamShopAccess).where(TeamShopAccess.team_id == team_id),
        )
        if credential_ids:
            session.execute(
                delete(PlatformCredential).where(
                    PlatformCredential.credential_id.in_(credential_ids),
                ),
            )
        session.execute(delete(Shop).where(Shop.shop_id.in_(shop_ids)))
        session.execute(delete(Device).where(Device.device_id == device_id))
        session.execute(delete(User).where(User.user_id == user_id))
        session.execute(delete(Team).where(Team.team_id == team_id))
        session.commit()


def _actor(*, team_id: UUID, user_id: UUID) -> ActorContext:
    return ActorContext(
        user_id=user_id,
        user_display_name="Task Account Integration User",
        team_id=team_id,
        membership_id=uuid4(),
        role_code="member",
        data_scope=DataScope.TEAM,
    )


def test_shop_scoped_task_claim_delivers_account_without_persisting_it(
    postgresql_engine: Engine,
) -> None:
    device_id = uuid4()
    team_id = uuid4()
    user_id = uuid4()
    actor = _actor(team_id=team_id, user_id=user_id)
    shop_ids = [uuid4(), uuid4()]
    credential_ids: set[UUID] = set()
    now = datetime.now(UTC)
    cipher = SecretCipher(Fernet.generate_key().decode("ascii"))
    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    Team(team_id=team_id, name="Task Account Integration Team"),
                    User(
                        user_id=user_id,
                        display_name="Task Account Integration User",
                    ),
                ],
            )
            session.add(
                Device(
                    device_id=device_id,
                    team_id=team_id,
                    display_name="Task Account Fixture Device",
                    enabled=True,
                ),
            )
            session.add_all(
                [
                    Shop(
                        shop_id=shop_id,
                        display_name="中文同名店铺",
                        platform=ShopPlatform.DOUYIN,
                        enabled=True,
                    )
                    for position, shop_id in enumerate(shop_ids, start=1)
                ],
            )
            runtime = DeviceRuntime(
                device_id=device_id,
                worker_version="0.4.5",
                last_seen_at=now,
                started_at=now,
                connection_status="online",
            )
            session.add(runtime)
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
                    account_display="Task Account Fixture",
                    account_type="PersonalBasic",
                    enterprise_account=False,
                    last_discovered_at=now,
                    inventory_payload=inventory,
                ),
            )
            session.add_all(
                [
                    ShopDeviceBinding(
                        shop_id=shop_id,
                        device_id=device_id,
                        enabled=True,
                    )
                    for shop_id in shop_ids
                ],
            )
            session.flush()
            session.add_all(
                [
                    TeamDeviceAccess(team_id=team_id, device_id=device_id),
                    *[
                        TeamShopAccess(team_id=team_id, shop_id=shop_id)
                        for shop_id in shop_ids
                    ],
                ],
            )
            session.commit()

            credential_service = CredentialService(session, cipher)
            for position, shop_id in enumerate(shop_ids, start=1):
                credential = credential_service.create(
                    CredentialCreate(
                        shop_id=shop_id,
                        login_identifier=f"task-account-user-{position}",
                        secret=SecretStr(f"task-account-secret-{position}"),
                    ),
                )
                assert credential.credential_id is not None
                credential_ids.add(credential.credential_id)

            task_service = TaskService(
                session,
                credential_service=credential_service,
            )
            task = task_service.create(
                TaskCreate(
                    target_device_id=device_id,
                    shop_ids=shop_ids,
                    skill_id="yingdao.app.run",
                    input={"app_id": "task-account-safe-app", "params": {}},
                ),
                actor,
            )
            assert task.shop_ids == shop_ids
            assert task.input_json == {
                "app_id": "task-account-safe-app",
                "params": {},
            }
            assert "account" not in task.input_json

            claimed = task_service.claim_with_account(
                WorkerPrincipal(device_id=device_id),
                now=now,
            )
            assert claimed is not None
            assert [item.model_dump(mode="json") for item in claimed.accounts] == [
                {
                    "shop_id": str(shop_ids[0]),
                    "shop_name": None,
                    "platform_code": "douyin",
                    "login_identifier": "task-account-user-1",
                    "secret": "task-account-secret-1",
                    "preferred_verification_channel": "manual",
                },
                {
                    "shop_id": str(shop_ids[1]),
                    "shop_name": None,
                    "platform_code": "douyin",
                    "login_identifier": "task-account-user-2",
                    "secret": "task-account-secret-2",
                    "preferred_verification_channel": "manual",
                },
            ]

            class LegacyWorkerAccountPayload(BaseModel):
                model_config = ConfigDict(extra="forbid")

                shop_id: str
                platform_code: str
                login_identifier: str
                secret: str
                preferred_verification_channel: str

            for account in claimed.accounts:
                LegacyWorkerAccountPayload.model_validate(
                    account.model_dump(mode="json", exclude_defaults=True),
                )

            completed = task_service.complete(
                WorkerPrincipal(device_id=device_id),
                task.task_id,
                TaskComplete(
                    result={
                        "ok": True,
                        "店铺列表": [
                            {"登录账号": "must-not-persist", "登录密码": "secret"},
                        ],
                    },
                ),
                now=now,
            )
            assert completed.result_json == {
                "ok": True,
                "店铺列表": "[ACCOUNT_PAYLOAD_REDACTED]",
            }

            runtime.worker_version = "0.4.7"
            session.commit()
            upgraded_task = task_service.create(
                TaskCreate(
                    target_device_id=device_id,
                    shop_ids=shop_ids,
                    skill_id="yingdao.app.run",
                    input={"app_id": "task-account-safe-app", "params": {}},
                ),
                actor,
            )
            upgraded_claimed = task_service.claim_with_account(
                WorkerPrincipal(device_id=device_id),
                now=now,
            )
            assert upgraded_claimed is not None
            assert upgraded_claimed.task.task_id == upgraded_task.task_id
            assert [item.model_dump(mode="json") for item in upgraded_claimed.accounts] == [
                {
                    "shop_id": str(shop_id),
                    "shop_name": "中文同名店铺",
                    "platform_code": "douyin",
                    "login_identifier": f"task-account-user-{position}",
                    "secret": f"task-account-secret-{position}",
                    "preferred_verification_channel": "manual",
                }
                for position, shop_id in enumerate(shop_ids, start=1)
            ]
    finally:
        _cleanup(
            postgresql_engine,
            device_id=device_id,
            shop_ids=set(shop_ids),
            credential_ids=credential_ids,
            team_id=team_id,
            user_id=user_id,
        )


def test_no_shop_task_claim_returns_an_empty_account_payload(
    postgresql_engine: Engine,
) -> None:
    device_id = uuid4()
    team_id = uuid4()
    user_id = uuid4()
    actor = _actor(team_id=team_id, user_id=user_id)
    now = datetime.now(UTC)
    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    Team(team_id=team_id, name="No Shop Task Integration Team"),
                    User(
                        user_id=user_id,
                        display_name="No Shop Task Integration User",
                    ),
                    Device(
                        device_id=device_id,
                        team_id=team_id,
                        display_name="No Shop Task Fixture Device",
                        enabled=True,
                    ),
                    DeviceRuntime(
                        device_id=device_id,
                        worker_version="0.4.7",
                        last_seen_at=now,
                        started_at=now,
                        connection_status="online",
                    ),
                    DeviceSkillCapability(
                        device_id=device_id,
                        skill_id="system.echo",
                        display_name="System Echo",
                        runtime="python",
                        provider_code=None,
                        skill_version="1",
                        classification="internal",
                    ),
                ],
            )
            session.flush()
            session.add(TeamDeviceAccess(team_id=team_id, device_id=device_id))
            session.commit()

            task_service = TaskService(session)
            task = task_service.create(
                TaskCreate(
                    target_device_id=device_id,
                    shop_ids=[],
                    skill_id="system.echo",
                    input={"message": "no shop context"},
                ),
                actor,
            )
            assert task.shop_ids == []

            claimed = task_service.claim_with_account(
                WorkerPrincipal(device_id=device_id),
                now=now,
            )
            assert claimed is not None
            assert claimed.task.task_id == task.task_id
            assert claimed.accounts == []
    finally:
        _cleanup(
            postgresql_engine,
            device_id=device_id,
            shop_ids=set(),
            credential_ids=set(),
            team_id=team_id,
            user_id=user_id,
        )


def test_no_shop_schedule_create_edit_and_trigger_keep_accounts_empty(
    postgresql_engine: Engine,
) -> None:
    device_id = uuid4()
    team_id = uuid4()
    user_id = uuid4()
    actor = _actor(team_id=team_id, user_id=user_id)
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    Team(team_id=team_id, name="No Shop Schedule Integration Team"),
                    User(
                        user_id=user_id,
                        display_name="No Shop Schedule Integration User",
                    ),
                    Device(
                        device_id=device_id,
                        team_id=team_id,
                        display_name="No Shop Schedule Fixture Device",
                        enabled=True,
                    ),
                    DeviceRuntime(
                        device_id=device_id,
                        worker_version="0.4.7",
                        last_seen_at=now,
                        started_at=now,
                        connection_status="online",
                    ),
                    DeviceSkillCapability(
                        device_id=device_id,
                        skill_id="system.echo",
                        display_name="System Echo",
                        runtime="python",
                        provider_code=None,
                        skill_version="1",
                        classification="business",
                        input_schema={
                            "type": "object",
                            "properties": {"message": {"type": "string"}},
                            "required": ["message"],
                            "additionalProperties": False,
                        },
                    ),
                ],
            )
            session.flush()
            session.add(TeamDeviceAccess(team_id=team_id, device_id=device_id))
            session.commit()

            schedules = ScheduleService(session)
            created = schedules.create(
                ScheduleCreate(
                    name="No Shop Schedule",
                    target_device_id=device_id,
                    shop_ids=[],
                    execution_type=ScheduleExecutionType.BUSINESS_SKILL,
                    skill_id="system.echo",
                    parameters={"message": "no shop context"},
                    local_time=time(9, 0),
                    timezone="Asia/Shanghai",
                ),
                actor,
                now=now,
            )
            assert created.shop_ids == []

            edited = schedules.update(
                created.schedule_id,
                ScheduleUpdate(shop_ids=[]),
                actor,
                now=now,
            )
            assert edited.shop_ids == []

            schedule = session.get(Schedule, created.schedule_id)
            assert schedule is not None
            schedule.next_run_at = now
            session.commit()

        with Session(postgresql_engine, expire_on_commit=False) as session:
            triggered = ScheduleService(session).trigger_next_due(now=now)
            assert triggered is not None
            assert triggered.task_id is not None
            task = session.get(Task, triggered.task_id)
            assert task is not None
            assert task.shop_ids == []
            claimed = TaskService(session).claim_with_account(
                WorkerPrincipal(device_id=device_id),
                now=now,
            )
            assert claimed is not None
            assert claimed.task.task_id == task.task_id
            assert claimed.accounts == []
    finally:
        _cleanup(
            postgresql_engine,
            device_id=device_id,
            shop_ids=set(),
            credential_ids=set(),
            team_id=team_id,
            user_id=user_id,
        )


def test_same_shop_can_run_on_two_bound_devices_without_global_lock(
    postgresql_engine: Engine,
) -> None:
    device_ids = [uuid4(), uuid4()]
    shop_id = uuid4()
    team_id = uuid4()
    user_id = uuid4()
    actor = _actor(team_id=team_id, user_id=user_id)
    credential_ids: set[UUID] = set()
    now = datetime.now(UTC)
    cipher = SecretCipher(Fernet.generate_key().decode("ascii"))
    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    Team(team_id=team_id, name="Shared Shop Integration Team"),
                    User(
                        user_id=user_id,
                        display_name="Shared Shop Integration User",
                    ),
                ],
            )
            session.add(
                Shop(
                    shop_id=shop_id,
                    display_name="Shared Shop Fixture",
                    platform=ShopPlatform.DOUYIN,
                    enabled=True,
                ),
            )
            session.add_all(
                [
                    Device(
                        device_id=device_id,
                        team_id=team_id,
                        display_name=f"Shared Shop Device {position}",
                        enabled=True,
                    )
                    for position, device_id in enumerate(device_ids, start=1)
                ],
            )
            session.add_all(
                [
                    DeviceRuntime(
                        device_id=device_id,
                        worker_version="0.4.5",
                        last_seen_at=now,
                        started_at=now,
                        connection_status="online",
                    )
                    for device_id in device_ids
                ],
            )
            session.flush()
            session.add_all(
                [
                    DeviceSkillCapability(
                        device_id=device_id,
                        skill_id="system.echo",
                        display_name="System Echo",
                        runtime="python",
                        provider_code=None,
                        skill_version="1",
                        classification="internal",
                    )
                    for device_id in device_ids
                ],
            )
            session.flush()
            session.add_all(
                [
                    ShopDeviceBinding(
                        shop_id=shop_id,
                        device_id=device_id,
                        enabled=True,
                    )
                    for device_id in device_ids
                ],
            )
            session.add_all(
                [
                    *[
                        TeamDeviceAccess(team_id=team_id, device_id=device_id)
                        for device_id in device_ids
                    ],
                    TeamShopAccess(team_id=team_id, shop_id=shop_id),
                ],
            )
            session.commit()

            credential_service = CredentialService(session, cipher)
            credential = credential_service.create(
                CredentialCreate(
                    shop_id=shop_id,
                    login_identifier="shared-shop-user",
                    secret=SecretStr("shared-shop-secret"),
                ),
            )
            assert credential.credential_id is not None
            credential_ids.add(credential.credential_id)

            task_service = TaskService(
                session,
                credential_service=credential_service,
            )
            first_task = task_service.create(
                TaskCreate(
                    target_device_id=device_ids[0],
                    shop_ids=[shop_id],
                    skill_id="system.echo",
                    input={"message": "first device"},
                ),
                actor,
            )
            claimed = task_service.claim_with_account(
                WorkerPrincipal(device_id=device_ids[0]),
                now=now,
            )
            assert claimed is not None
            assert claimed.task.task_id == first_task.task_id
            assert claimed.task.status == "running"

            second_task = task_service.create(
                TaskCreate(
                    target_device_id=device_ids[1],
                    shop_ids=[shop_id],
                    skill_id="system.echo",
                    input={"message": "second device"},
                ),
                actor,
            )
            assert second_task.target_device_id == device_ids[1]
            assert second_task.shop_ids == [shop_id]
            assert second_task.status == "pending"
            assert session.query(Task).filter(
                Task.task_id.in_([first_task.task_id, second_task.task_id]),
            ).count() == 2
    finally:
        with Session(postgresql_engine) as session:
            task_ids = session.query(Task.task_id).where(
                Task.target_device_id.in_(device_ids),
            )
            session.execute(delete(TaskEvent).where(TaskEvent.task_id.in_(task_ids)))
            session.execute(delete(TaskShop).where(TaskShop.task_id.in_(task_ids)))
            session.execute(delete(Task).where(Task.target_device_id.in_(device_ids)))
            session.execute(
                delete(DeviceProviderInventory).where(
                    DeviceProviderInventory.device_id.in_(device_ids),
                ),
            )
            session.execute(
                delete(DeviceSkillCapability).where(
                    DeviceSkillCapability.device_id.in_(device_ids),
                ),
            )
            session.execute(
                delete(DeviceRuntime).where(DeviceRuntime.device_id.in_(device_ids)),
            )
            session.execute(
                delete(ShopCredentialBinding).where(
                    ShopCredentialBinding.shop_id == shop_id,
                ),
            )
            session.execute(
                delete(ShopDeviceBinding).where(
                    ShopDeviceBinding.shop_id == shop_id,
                ),
            )
            session.execute(
                delete(TeamDeviceAccess).where(
                    TeamDeviceAccess.team_id == team_id,
                ),
            )
            session.execute(
                delete(TeamShopAccess).where(
                    TeamShopAccess.team_id == team_id,
                ),
            )
            if credential_ids:
                session.execute(
                    delete(PlatformCredential).where(
                        PlatformCredential.credential_id.in_(credential_ids),
                    ),
                )
            session.execute(delete(Shop).where(Shop.shop_id == shop_id))
            session.execute(delete(Device).where(Device.device_id.in_(device_ids)))
            session.execute(delete(User).where(User.user_id == user_id))
            session.execute(delete(Team).where(Team.team_id == team_id))
            session.commit()
