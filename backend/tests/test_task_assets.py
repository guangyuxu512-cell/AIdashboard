from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.assets.enums import AssetMediaType, AssetSourceType
from app.modules.assets.models import Asset
from app.modules.devices.models import Device
from app.modules.tasks.enums import TaskSkillId
from app.modules.tasks.exceptions import TaskAssetInvalidError
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import TaskService
from app.modules.tasks.worker_api import claim_task
from app.modules.workers.models import DeviceSkillCapability
from app.modules.workers.service import WorkerPrincipal
from tests.support import AllowExecutionResources, FakeSession


ACTOR = ActorContext(
    user_id=uuid4(),
    user_display_name="任务图片测试人员",
    team_id=uuid4(),
    membership_id=uuid4(),
    role_code="member",
    data_scope=DataScope.TEAM,
)


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

    def get_task_target_device(
        self,
        device_id: UUID,
        *,
        team_id: UUID | None = None,
    ) -> Device | None:
        del team_id
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
        return [
            self.assets[asset_id] for asset_id in asset_ids if asset_id in self.assets
        ]


def make_asset(name: str) -> Asset:
    return Asset(
        asset_id=uuid4(),
        team_id=ACTOR.team_id,
        created_by_user_id=None,
        original_filename=name,
        storage_key=f"{uuid4().hex}.jpg",
        media_type=AssetMediaType.IMAGE.value,
        source_type=AssetSourceType.UPLOAD.value,
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
        team_authorization_service=AllowExecutionResources(),  # type: ignore[arg-type]
    )
    ordered_ids = [third.asset_id, first.asset_id, second.asset_id]

    task = service.create(make_request(device.device_id, ordered_ids), ACTOR)

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
        team_authorization_service=AllowExecutionResources(),  # type: ignore[arg-type]
    )

    with pytest.raises(TaskAssetInvalidError) as captured:
        service.create(
            make_request(device.device_id, [existing.asset_id, missing_id]),
            ACTOR,
        )

    assert repository.tasks == []
    assert captured.value.details == {"asset_ids": [str(missing_id)]}


def test_non_image_asset_is_not_added_to_worker_task_contract() -> None:
    device = Device(device_id=uuid4(), display_name="图片测试设备", enabled=True)
    future_video = make_asset("future.jpg")
    future_video.media_type = AssetMediaType.VIDEO.value
    repository = FakeTaskRepository(device)
    service = TaskService(
        FakeSession(),  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
        asset_repository=FakeAssetRepository([future_video]),  # type: ignore[arg-type]
        team_authorization_service=AllowExecutionResources(),  # type: ignore[arg-type]
    )

    with pytest.raises(TaskAssetInvalidError) as captured:
        service.create(make_request(device.device_id, [future_video.asset_id]), ACTOR)

    assert repository.tasks == []
    assert captured.value.details == {"asset_ids": [str(future_video.asset_id)]}


def test_worker_claim_asset_contract_remains_v1_compatible() -> None:
    device_id = uuid4()
    task_id = uuid4()
    asset = make_asset("worker.jpg")
    task = SimpleNamespace(
        task_id=task_id,
        skill_id=TaskSkillId.SYSTEM_ECHO,
        input_json={"message": "asset-contract"},
        lease_until=datetime.now(UTC),
    )
    service = SimpleNamespace(
        claim_with_account=lambda _principal, **_kwargs: SimpleNamespace(
            task=task,
            accounts=[],
            assets=[asset],
        ),
    )

    response = claim_task(
        WorkerPrincipal(device_id=device_id),
        service,  # type: ignore[arg-type]
    )

    assert not isinstance(response, type(None))
    payload = response.assets[0].model_dump(mode="json")  # type: ignore[union-attr]
    assert set(payload) == {
        "asset_id",
        "filename",
        "position",
        "content_type",
        "size_bytes",
        "sha256",
        "download_path",
    }
    assert payload["download_path"] == (
        f"/api/v1/worker/tasks/{task_id}/assets/{asset.asset_id}"
    )


def test_duplicate_asset_ids_are_rejected_by_contract() -> None:
    asset_id = uuid4()
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        make_request(uuid4(), [asset_id, asset_id])
