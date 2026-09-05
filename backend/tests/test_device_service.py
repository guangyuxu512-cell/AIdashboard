from uuid import UUID, uuid4

import pytest

from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.devices.exceptions import DeviceHasActiveTasksError, DeviceNotFoundError
from app.modules.devices.models import Device
from app.modules.devices.schemas import DeviceCreate, DeviceUpdate
from app.modules.devices.service import DeviceService
from tests.support import FakeSession


class FakeDeviceRepository:
    def __init__(self) -> None:
        self.items: dict[object, Device] = {}

    def list(
        self,
        *,
        actor: ActorContext,
        offset: int,
        limit: int,
    ) -> list[Device]:
        del actor
        return [
            item for item in self.items.values() if item.deleted_at is None
        ][offset : offset + limit]

    def count(self, *, actor: ActorContext) -> int:
        del actor
        return sum(item.deleted_at is None for item in self.items.values())

    def get_for_actor(
        self,
        *,
        actor: ActorContext,
        device_id: object,
    ) -> Device | None:
        del actor
        device = self.items.get(device_id)
        return device if device is not None and device.deleted_at is None else None

    def get_for_actor_for_update(
        self,
        *,
        actor: ActorContext,
        device_id: object,
    ) -> Device | None:
        return self.get_for_actor(actor=actor, device_id=device_id)

    def get_including_deleted(self, device_id: object) -> Device | None:
        return self.items.get(device_id)

    def add(self, device: Device) -> None:
        if device.device_id is None:
            device.device_id = uuid4()
        self.items[device.device_id] = device


ACTOR = ActorContext(
    user_id=UUID("10000000-0000-4000-8000-000000000001"),
    user_display_name="设备测试人员",
    team_id=UUID("20000000-0000-4000-8000-000000000001"),
    membership_id=UUID("30000000-0000-4000-8000-000000000001"),
    role_code="member",
    data_scope=DataScope.TEAM,
)


class FakeBindingRepository:
    def __init__(self) -> None:
        self.disabled: list[object] = []

    def disable_enabled_by_device(self, device_id: object) -> int:
        self.disabled.append(device_id)
        return 1


class FakeTaskRepository:
    def __init__(self, active: bool = False) -> None:
        self.active = active

    def has_active_for_device(self, device_id: object) -> bool:
        del device_id
        return self.active


class FakeWorkerRepository:
    def __init__(self) -> None:
        self.revoked: list[object] = []

    def disable_credentials_by_device(self, device_id: object) -> int:
        self.revoked.append(device_id)
        return 1


def test_device_create_get_list_and_update() -> None:
    session = FakeSession()
    repository = FakeDeviceRepository()
    service = DeviceService(session, repository)  # type: ignore[arg-type]

    created = service.create(
        ACTOR,
        DeviceCreate(display_name="执行设备 01", location="杭州", note="基础设备"),
    )
    fetched = service.get(ACTOR, created.device_id)
    items, total = service.list(actor=ACTOR, offset=0, limit=20)
    updated = service.update(
        ACTOR,
        created.device_id,
        DeviceUpdate(display_name="执行设备 01A", enabled=False),
    )

    assert fetched is created
    assert items == [created]
    assert total == 1
    assert updated.display_name == "执行设备 01A"
    assert updated.enabled is False
    assert created.team_id == ACTOR.team_id
    assert created.created_by_user_id == ACTOR.user_id
    assert session.commits == 2


def test_device_not_found() -> None:
    service = DeviceService(  # type: ignore[arg-type]
        FakeSession(),
        FakeDeviceRepository(),
    )

    with pytest.raises(DeviceNotFoundError):
        service.get(ACTOR, uuid4())


def test_device_soft_remove_disables_bindings_and_revokes_worker_token() -> None:
    session = FakeSession()
    repository = FakeDeviceRepository()
    bindings = FakeBindingRepository()
    tasks = FakeTaskRepository()
    workers = FakeWorkerRepository()
    service = DeviceService(  # type: ignore[arg-type]
        session,
        repository,
        bindings,
        tasks,
        workers,
    )
    device = service.create(ACTOR, DeviceCreate(display_name="待移除设备"))

    service.remove(ACTOR, device.device_id)

    stored = repository.get_including_deleted(device.device_id)
    assert stored is not None
    assert stored.enabled is False
    assert stored.deleted_at is not None
    assert repository.get_for_actor(actor=ACTOR, device_id=device.device_id) is None
    assert bindings.disabled == [device.device_id]
    assert workers.revoked == [device.device_id]


def test_device_soft_remove_rejects_active_tasks_without_side_effects() -> None:
    session = FakeSession()
    repository = FakeDeviceRepository()
    bindings = FakeBindingRepository()
    tasks = FakeTaskRepository(active=True)
    workers = FakeWorkerRepository()
    service = DeviceService(  # type: ignore[arg-type]
        session,
        repository,
        bindings,
        tasks,
        workers,
    )
    device = service.create(ACTOR, DeviceCreate(display_name="活动任务设备"))

    with pytest.raises(DeviceHasActiveTasksError):
        service.remove(ACTOR, device.device_id)

    assert device.enabled is True
    assert device.deleted_at is None
    assert bindings.disabled == []
    assert workers.revoked == []
