from uuid import uuid4

import pytest

from app.modules.devices.exceptions import DeviceNotFoundError
from app.modules.devices.models import Device
from app.modules.devices.schemas import DeviceCreate, DeviceUpdate
from app.modules.devices.service import DeviceService
from tests.support import FakeSession


class FakeDeviceRepository:
    def __init__(self) -> None:
        self.items: dict[object, Device] = {}

    def list(self, *, offset: int, limit: int) -> list[Device]:
        return list(self.items.values())[offset : offset + limit]

    def count(self) -> int:
        return len(self.items)

    def get(self, device_id: object) -> Device | None:
        return self.items.get(device_id)

    def add(self, device: Device) -> None:
        if device.device_id is None:
            device.device_id = uuid4()
        self.items[device.device_id] = device


def test_device_create_get_list_and_update() -> None:
    session = FakeSession()
    repository = FakeDeviceRepository()
    service = DeviceService(session, repository)  # type: ignore[arg-type]

    created = service.create(
        DeviceCreate(display_name="执行设备 01", location="杭州", note="基础设备"),
    )
    fetched = service.get(created.device_id)
    items, total = service.list(offset=0, limit=20)
    updated = service.update(
        created.device_id,
        DeviceUpdate(display_name="执行设备 01A", enabled=False),
    )

    assert fetched is created
    assert items == [created]
    assert total == 1
    assert updated.display_name == "执行设备 01A"
    assert updated.enabled is False
    assert session.commits == 2


def test_device_not_found() -> None:
    service = DeviceService(  # type: ignore[arg-type]
        FakeSession(),
        FakeDeviceRepository(),
    )

    with pytest.raises(DeviceNotFoundError):
        service.get(uuid4())
