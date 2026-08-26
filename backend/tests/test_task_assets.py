from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.modules.assets.models import Asset
from app.modules.devices.models import Device
from app.modules.tasks.enums import TaskSkillId
from app.modules.tasks.exceptions import TaskAssetInvalidError
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import TaskService
from app.modules.workers.models import DeviceSkillCapability
from tests.support import FakeSession


class FakeTaskRepository:
    def __init__(self, device: Device) -> None:
        self.device = device
        self.tasks: list[object] = []
        self.capability = DeviceSkillCapability(
            device_id=device.device_id,
            skill_id=TaskSkillId.SYSTEM_ECHO,
            display_name="安全回显",
            runtime="python",
            provider_code=None,
            skill_version="1",
            classification="internal",
        )

    def get_task_target_device(self, device_id: UUID) -> Device | None:
        return self.device if device_id == self.device.device_id else None

    def get_device_runtime(self, device_id: UUID) -> object | None:
        return SimpleNamespace(connection_status="online")

    def get_skill_capability(
        self,
        device_id: UUID,
        skill_id: str,
    ) -> DeviceSkillCapability | None:
        return self.capability if device_id == self.device.device_id else None

    def add(self, task: object) -> None:
        self.tasks.append(task)


class FakeAssetRepository:
    def __init__(self, assets: list[Asset]) -> None:
        self.assets = {asset.asset_id: asset for asset in assets}

    def list_by_ids(self, asset_ids: list[UUID]) -> list[Asset]:
        return [self.assets[asset_id] for asset_id in asset_ids if asset_id in self.assets]


def make_asset(name: str) -> Asset:
    return Asset(
        asset_id=uuid4(),
        original_filename=name,
        storage_key=f"{uuid4().hex}.jpg",
        content_type="image/jpeg",
        size_bytes=10,
        sha256="a" * 64,
    )


def make_request(device_id: UUID, asset_ids: list[UUID]) -> TaskCreate:
    return TaskCreate(
        target_device_id=device_id,
        asset_ids=asset_ids,
        skill_id=TaskSkillId.SYSTEM_ECHO,
        input={"message": "asset-order"},
    )


def test_one_task_keeps_ordered_asset_relationships() -> None:
    device = Device(device_id=uuid4(), display_name="图片测试设备", enabled=True)
    first, second, third = make_asset("1.jpg"), make_asset("2.jpg"), make_asset("3.jpg")
    repository = FakeTaskRepository(device)
    service = TaskService(
        FakeSession(),  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
        asset_repository=FakeAssetRepository([first, second, third]),  # type: ignore[arg-type]
    )
    ordered_ids = [third.asset_id, first.asset_id, second.asset_id]

    task = service.create(make_request(device.device_id, ordered_ids))

    assert repository.tasks == [task]
    assert task.asset_ids == ordered_ids
    assert [link.position for link in task.asset_links] == [0, 1, 2]


def test_missing_asset_rejects_the_whole_task() -> None:
    device = Device(device_id=uuid4(), display_name="图片测试设备", enabled=True)
    existing = make_asset("exists.jpg")
    missing_id = uuid4()
    repository = FakeTaskRepository(device)
    service = TaskService(
        FakeSession(),  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
        asset_repository=FakeAssetRepository([existing]),  # type: ignore[arg-type]
    )

    with pytest.raises(TaskAssetInvalidError) as captured:
        service.create(
            make_request(device.device_id, [existing.asset_id, missing_id]),
        )

    assert repository.tasks == []
    assert captured.value.details == {"asset_ids": [str(missing_id)]}


def test_duplicate_asset_ids_are_rejected_by_contract() -> None:
    asset_id = uuid4()
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        make_request(uuid4(), [asset_id, asset_id])
