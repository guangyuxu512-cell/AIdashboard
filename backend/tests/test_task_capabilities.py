from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.devices.models import Device
from app.modules.tasks.enums import TaskSkillId
from app.modules.tasks.exceptions import (
    TaskApplicationNotAvailableError,
    TaskDeviceDisabledError,
    TaskProviderLoginRequiredError,
    TaskProviderNotReadyError,
    TaskProviderVersionUnsupportedError,
    TaskSkillNotAvailableError,
    TaskWorkerOfflineError,
)
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import TaskService
from app.modules.workers.models import DeviceProviderInventory, DeviceSkillCapability
from tests.support import FakeSession


class FakeTaskCapabilityRepository:
    def __init__(
        self,
        device: Device,
        capabilities: list[DeviceSkillCapability],
        inventory_payload: dict[str, object] | None = None,
        runtime_status: str = "online",
    ) -> None:
        self.device = device
        self.capabilities = {
            capability.skill_id: capability for capability in capabilities
        }
        self.inventory = (
            DeviceProviderInventory(
                device_id=device.device_id,
                provider_code="yingdao",
                available=bool(inventory_payload and inventory_payload.get("available")),
                provider_version=(
                    str(inventory_payload.get("provider_version"))
                    if inventory_payload and inventory_payload.get("provider_version")
                    else None
                ),
                account_display=None,
                account_type=None,
                enterprise_account=None,
                last_discovered_at=datetime.now(UTC),
                inventory_payload=inventory_payload,
            )
            if inventory_payload is not None
            else None
        )
        self.tasks: list[object] = []
        self.runtime_status = runtime_status

    def get_task_target_device(self, device_id: object) -> Device | None:
        if device_id == self.device.device_id and self.device.deleted_at is None:
            return self.device
        return None

    def get_skill_capability(
        self,
        device_id: object,
        skill_id: str,
    ) -> DeviceSkillCapability | None:
        return (
            self.capabilities.get(skill_id)
            if device_id == self.device.device_id
            else None
        )

    def get_device_runtime(self, device_id: object) -> object | None:
        if device_id != self.device.device_id:
            return None
        return SimpleNamespace(connection_status=self.runtime_status)

    def get_provider_inventory(
        self,
        device_id: object,
        provider_code: str,
    ) -> DeviceProviderInventory | None:
        if device_id == self.device.device_id and provider_code == "yingdao":
            return self.inventory
        return None

    def add(self, task: object) -> None:
        self.tasks.append(task)


class EmptyApplicationConfigRepository:
    def get(self, provider_code: str, app_id: str) -> None:
        del provider_code, app_id
        return None


def capability(
    device: Device,
    skill_id: str,
    *,
    runtime: str = "python",
    provider: str | None = None,
) -> DeviceSkillCapability:
    return DeviceSkillCapability(
        device_id=device.device_id,
        skill_id=skill_id,
        display_name=skill_id,
        runtime=runtime,
        provider_code=provider,
        skill_version="1",
        classification="internal",
    )


def ready_inventory(*, include_app: bool = True) -> dict[str, object]:
    return {
        "provider": "yingdao",
        "available": True,
        # Intentionally legacy: the status field was absent in existing rows.
        "provider_version": "6.3.6",
        "execution_available": True,
        "execution_version": "6.3.6",
        "logged_in": True,
        "account_display": "GY00999",
        "account_type": "PersonalBasic",
        "enterprise_account": False,
        "user_id": "906515367141965826",
        "applications": (
            [
                {
                    "app_id": "safe-app",
                    "app_name": "Safe App",
                    "version_id": "1",
                    "updated_at": None,
                    "app_type": None,
                    "group_id": None,
                },
            ]
            if include_app
            else []
        ),
        "discovered_at": datetime.now(UTC).isoformat(),
    }


def service_for(
    device: Device,
    capabilities: list[DeviceSkillCapability],
    inventory: dict[str, object] | None = None,
    *,
    runtime_status: str = "online",
) -> TaskService:
    return TaskService(
        FakeSession(),  # type: ignore[arg-type]
        FakeTaskCapabilityRepository(  # type: ignore[arg-type]
            device,
            capabilities,
            inventory,
            runtime_status,
        ),
        application_config_repository=EmptyApplicationConfigRepository(),  # type: ignore[arg-type]
    )


def test_system_skill_requires_device_capability_and_disabled_is_distinct() -> None:
    device = Device(device_id=uuid4(), display_name="PC-11", enabled=True)
    with pytest.raises(TaskSkillNotAvailableError):
        service_for(device, []).create(
            TaskCreate(
                target_device_id=device.device_id,
                skill_id=TaskSkillId.SYSTEM_ECHO,
                input={"message": "hello"},
            ),
        )

    device.enabled = False
    with pytest.raises(TaskDeviceDisabledError):
        service_for(device, [capability(device, "system.echo")]).create(
            TaskCreate(
                target_device_id=device.device_id,
                skill_id=TaskSkillId.SYSTEM_ECHO,
                input={"message": "hello"},
            ),
        )


def test_offline_device_cannot_create_an_immediate_task() -> None:
    device = Device(device_id=uuid4(), display_name="PC-11", enabled=True)
    with pytest.raises(TaskWorkerOfflineError):
        service_for(
            device,
            [capability(device, "system.echo")],
            runtime_status="offline",
        ).create(
            TaskCreate(
                target_device_id=device.device_id,
                skill_id=TaskSkillId.SYSTEM_ECHO,
                input={"message": "hello"},
            ),
        )


def test_offline_device_can_prepare_and_create_a_scheduled_task() -> None:
    device = Device(device_id=uuid4(), display_name="PC-11", enabled=True)
    service = service_for(
        device,
        [capability(device, "system.echo")],
        runtime_status="offline",
    )
    request = TaskCreate(
        target_device_id=device.device_id,
        skill_id=TaskSkillId.SYSTEM_ECHO,
        input={"message": "scheduled"},
    )

    prepared = service.prepare_scheduled_task(request)
    task = service.create_for_schedule(request)

    assert prepared.execution_display_name == "system.echo"
    assert task.status == "pending"
    assert task.input_json == {"message": "scheduled"}

def test_legacy_ready_provider_inventory_allows_yingdao_app_guard() -> None:
    device = Device(device_id=uuid4(), display_name="PC-11", enabled=True)
    task = service_for(
        device,
        [capability(device, "yingdao.app.run", runtime="rpa", provider="yingdao")],
        ready_inventory(),
    ).create(
        TaskCreate(
            target_device_id=device.device_id,
            skill_id=TaskSkillId.YINGDAO_APP_RUN,
            input={"app_id": "safe-app", "params": {}},
        ),
    )
    assert task.skill_id == "yingdao.app.run"
    assert task.execution_display_name == "Safe App"


def test_yingdao_guard_returns_specific_provider_and_application_errors() -> None:
    device = Device(device_id=uuid4(), display_name="PC-11", enabled=True)
    skill = capability(
        device,
        "yingdao.app.run",
        runtime="rpa",
        provider="yingdao",
    )
    request = TaskCreate(
        target_device_id=device.device_id,
        skill_id=TaskSkillId.YINGDAO_APP_RUN,
        input={"app_id": "safe-app", "params": {}},
    )

    with pytest.raises(TaskProviderNotReadyError):
        service_for(device, [skill]).create(request)

    login = ready_inventory()
    login.update(
        status="need_login",
        available=False,
        execution_available=False,
        execution_version=None,
        logged_in=False,
        user_id=None,
    )
    with pytest.raises(TaskProviderLoginRequiredError):
        service_for(device, [skill], login).create(request)

    unsupported = ready_inventory()
    unsupported.update(
        status="version_unsupported",
        available=False,
        provider_version="6.3.9",
        execution_available=False,
        execution_version=None,
    )
    with pytest.raises(TaskProviderVersionUnsupportedError):
        service_for(device, [skill], unsupported).create(request)

    with pytest.raises(TaskApplicationNotAvailableError):
        service_for(device, [skill], ready_inventory(include_app=False)).create(request)


def test_discovery_skill_does_not_require_ready_provider() -> None:
    device = Device(device_id=uuid4(), display_name="PC-11", enabled=True)
    task = service_for(
        device,
        [
            capability(
                device,
                "yingdao.discover",
                runtime="discovery",
                provider="yingdao",
            ),
        ],
    ).create(
        TaskCreate(
            target_device_id=device.device_id,
            skill_id=TaskSkillId.YINGDAO_DISCOVER,
            input={},
        ),
    )
    assert task.skill_id == "yingdao.discover"
