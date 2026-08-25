from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from app.core.security import SecretCipher
from app.modules.credentials.models import PlatformCredential, ShopCredentialBinding
from app.modules.credentials.schemas import CredentialCreate
from app.modules.credentials.service import CredentialService
from app.modules.devices.models import Device
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.tasks.models import Task, TaskEvent
from app.modules.tasks.schemas import TaskComplete, TaskCreate
from app.modules.tasks.service import TaskService
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
    shop_id: UUID,
    credential_id: UUID | None,
) -> None:
    with Session(engine) as session:
        task_ids = session.query(Task.task_id).where(
            Task.target_device_id == device_id,
        )
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
        session.execute(delete(DeviceRuntime).where(DeviceRuntime.device_id == device_id))
        session.execute(
            delete(ShopCredentialBinding).where(
                ShopCredentialBinding.shop_id == shop_id,
            ),
        )
        if credential_id is not None:
            session.execute(
                delete(PlatformCredential).where(
                    PlatformCredential.credential_id == credential_id,
                ),
            )
        session.execute(delete(Shop).where(Shop.shop_id == shop_id))
        session.execute(delete(Device).where(Device.device_id == device_id))
        session.commit()


def test_shop_scoped_task_claim_delivers_account_without_persisting_it(
    postgresql_engine: Engine,
) -> None:
    device_id = uuid4()
    shop_id = uuid4()
    credential_id: UUID | None = None
    now = datetime.now(UTC)
    cipher = SecretCipher(Fernet.generate_key().decode("ascii"))
    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            session.add(
                Device(
                    device_id=device_id,
                    display_name="Task Account Fixture Device",
                    enabled=True,
                ),
            )
            session.add(
                Shop(
                    shop_id=shop_id,
                    display_name="Task Account Fixture Shop",
                    platform=ShopPlatform.DOUYIN,
                    enabled=True,
                ),
            )
            session.add(
                DeviceRuntime(
                    device_id=device_id,
                    worker_version="0.4.4",
                    last_seen_at=now,
                    started_at=now,
                    connection_status="online",
                ),
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
                    account_display="Task Account Fixture",
                    account_type="PersonalBasic",
                    enterprise_account=False,
                    last_discovered_at=now,
                    inventory_payload=inventory,
                ),
            )
            session.commit()

            credential_service = CredentialService(session, cipher)
            credential = credential_service.create(
                CredentialCreate(
                    shop_id=shop_id,
                    login_identifier="task-account-user",
                    secret=SecretStr("task-account-secret"),
                ),
            )
            credential_id = credential.credential_id
            assert credential_id is not None

            task_service = TaskService(
                session,
                credential_service=credential_service,
            )
            task = task_service.create(
                TaskCreate(
                    target_device_id=device_id,
                    shop_id=shop_id,
                    skill_id="yingdao.app.run",
                    input={"app_id": "task-account-safe-app", "params": {}},
                ),
            )
            assert task.shop_id == shop_id
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
            assert claimed.account is not None
            assert claimed.account.model_dump(mode="json") == {
                "shop_id": str(shop_id),
                "platform_code": "douyin",
                "login_identifier": "task-account-user",
                "secret": "task-account-secret",
                "preferred_verification_channel": "manual",
            }

            completed = task_service.complete(
                WorkerPrincipal(device_id=device_id),
                task.task_id,
                TaskComplete(
                    result={
                        "ok": True,
                        "account": {"secret": "must-not-persist"},
                    },
                ),
                now=now,
            )
            assert completed.result_json == {
                "ok": True,
                "account": "[REDACTED]",
            }
    finally:
        _cleanup(
            postgresql_engine,
            device_id=device_id,
            shop_id=shop_id,
            credential_id=credential_id,
        )
