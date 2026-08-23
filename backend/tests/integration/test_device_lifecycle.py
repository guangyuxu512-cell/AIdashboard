from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from app.modules.devices.exceptions import DeviceHasActiveTasksError
from app.modules.devices.models import Device
from app.modules.devices.repository import DeviceRepository
from app.modules.devices.schemas import DeviceCreate, DeviceUpdate
from app.modules.devices.service import DeviceService
from app.modules.shops.enums import BindingRole, ShopPlatform
from app.modules.shops.models import Shop, ShopDeviceBinding
from app.modules.tasks.enums import TaskSkillId, TaskStatus
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import TaskCreate, TaskFail
from app.modules.tasks.service import TaskService
from app.modules.workers.exceptions import WorkerAuthenticationError
from app.modules.workers.models import (
    DeviceProviderInventory,
    DeviceRuntime,
    DeviceSkillCapability,
    WorkerDeviceCredential,
)
from app.modules.workers.schemas import (
    SkillCapabilitySnapshotUpsert,
    WorkerHeartbeat,
)
from app.modules.workers.service import WorkerService


pytestmark = pytest.mark.integration


def test_device_soft_remove_preserves_history_and_revokes_execution_identity(
    postgresql_engine: Engine,
) -> None:
    device_id = uuid4()
    replacement_device_id = None
    shop_id = uuid4()
    task_id = None
    now = datetime.now(UTC)

    try:
        with Session(postgresql_engine) as session:
            session.add_all(
                [
                    Device(
                        device_id=device_id,
                        display_name="stage-device-lifecycle",
                        enabled=True,
                    ),
                    Shop(
                        shop_id=shop_id,
                        display_name="stage-device-lifecycle-shop",
                        platform=ShopPlatform.DOUYIN,
                        enabled=True,
                    ),
                ],
            )
            session.flush()
            session.add(
                ShopDeviceBinding(
                    shop_id=shop_id,
                    device_id=device_id,
                    binding_role=BindingRole.PRIMARY,
                    enabled=True,
                ),
            )
            session.add(
                DeviceProviderInventory(
                    device_id=device_id,
                    provider_code="yingdao",
                    available=True,
                    provider_version="6.3.6",
                    account_display="integration-account",
                    account_type="PersonalBasic",
                    enterprise_account=False,
                    last_discovered_at=now,
                    inventory_payload={
                        "provider": "yingdao",
                        "available": True,
                        "status": "ready",
                        "provider_version": "6.3.6",
                        "execution_available": True,
                        "execution_version": "6.3.6",
                        "logged_in": True,
                        "account_display": "integration-account",
                        "account_type": "PersonalBasic",
                        "enterprise_account": False,
                        "user_id": "integration-user",
                        "applications": [],
                        "discovered_at": now.isoformat(),
                    },
                ),
            )
            session.commit()

        with Session(postgresql_engine, expire_on_commit=False) as session:
            worker_service = WorkerService(session)
            token = worker_service.issue_token(device_id)
            principal = worker_service.authenticate(device_id, token)
            worker_service.heartbeat(
                principal,
                WorkerHeartbeat(worker_version="0.1.0", started_at=now),
                now=now,
            )
            worker_service.sync_skill_capabilities(
                principal,
                SkillCapabilitySnapshotUpsert.model_validate(
                    {
                        "skills": [
                            {
                                "skill_id": "system.echo",
                                "display_name": "Echo",
                                "runtime": "python",
                                "provider": None,
                                "version": "1",
                            },
                        ],
                    },
                ),
                now=now,
            )

            task_service = TaskService(session)
            task = task_service.create(
                TaskCreate(
                    target_device_id=device_id,
                    skill_id=TaskSkillId.SYSTEM_ECHO,
                    input={"message": "lifecycle"},
                ),
            )
            task_id = task.task_id

            DeviceService(session).update(device_id, DeviceUpdate(enabled=False))
            disabled_heartbeat = worker_service.heartbeat(
                principal,
                WorkerHeartbeat(worker_version="0.1.0", started_at=now),
                now=now,
            )
            assert disabled_heartbeat.connection_status == "online"
            assert task_service.claim(principal, now=now) is None
            DeviceService(session).update(device_id, DeviceUpdate(enabled=True))

            with pytest.raises(DeviceHasActiveTasksError):
                DeviceService(session).remove(device_id)
            assert task_service.claim(principal, now=now) is not None
            with pytest.raises(DeviceHasActiveTasksError):
                DeviceService(session).remove(device_id)

            failed = task_service.fail(
                principal,
                task.task_id,
                TaskFail(
                    error_code="INTEGRATION_TERMINAL",
                    error_message="terminal task permits removal",
                ),
                now=now,
            )
            assert failed.status == TaskStatus.FAILED.value
            DeviceService(session).remove(device_id)

            with pytest.raises(WorkerAuthenticationError):
                worker_service.authenticate(device_id, token)

        with Session(postgresql_engine) as session:
            stored = DeviceRepository(session).get_including_deleted(device_id)
            assert stored is not None
            assert stored.enabled is False
            assert stored.deleted_at is not None
            assert DeviceRepository(session).get(device_id) is None
            binding = session.get(ShopDeviceBinding, (shop_id, device_id))
            assert binding is not None and binding.enabled is False
            credential = session.query(WorkerDeviceCredential).filter_by(
                device_id=device_id,
            ).one()
            assert credential.enabled is False
            assert session.get(Task, task_id) is not None
            assert session.get(DeviceProviderInventory, (device_id, "yingdao")) is not None
            assert session.get(DeviceRuntime, device_id) is not None

            replacement = DeviceService(session).create(
                DeviceCreate(display_name="stage-device-lifecycle"),
            )
            replacement_device_id = replacement.device_id
            assert replacement.device_id != device_id
    finally:
        with Session(postgresql_engine) as session:
            session.execute(delete(Task).where(Task.target_device_id == device_id))
            session.execute(
                delete(DeviceSkillCapability).where(
                    DeviceSkillCapability.device_id == device_id,
                ),
            )
            session.execute(
                delete(DeviceProviderInventory).where(
                    DeviceProviderInventory.device_id == device_id,
                ),
            )
            session.execute(
                delete(DeviceRuntime).where(DeviceRuntime.device_id == device_id),
            )
            session.execute(
                delete(WorkerDeviceCredential).where(
                    WorkerDeviceCredential.device_id == device_id,
                ),
            )
            session.execute(
                delete(ShopDeviceBinding).where(
                    ShopDeviceBinding.device_id == device_id,
                ),
            )
            session.execute(delete(Device).where(Device.device_id == device_id))
            if replacement_device_id is not None:
                session.execute(
                    delete(Device).where(Device.device_id == replacement_device_id),
                )
            session.execute(delete(Shop).where(Shop.shop_id == shop_id))
            session.commit()
