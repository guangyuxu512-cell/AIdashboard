from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.credentials.exceptions import CredentialNotFoundError
from app.modules.devices.models import Device
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.tasks.enums import TaskSkillId
from app.modules.tasks.exceptions import (
    TaskShopDeviceBindingInvalidError,
    TaskShopInvalidError,
)
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import TaskService
from app.modules.workers.models import DeviceSkillCapability
from tests.support import FakeSession


ACTOR = ActorContext(
    user_id=uuid4(),
    user_display_name="多店铺任务测试人员",
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
        if device_id != self.device.device_id:
            return None
        return SimpleNamespace(connection_status="online")

    def get_skill_capability(
        self,
        device_id: UUID,
        skill_id: str,
    ) -> DeviceSkillCapability | None:
        if device_id == self.device.device_id and skill_id == self.capability.skill_id:
            return self.capability
        return None

    def add(self, task: object) -> None:
        self.tasks.append(task)


class FakeShopRepository:
    def __init__(self, shops: list[Shop]) -> None:
        self.shops = {shop.shop_id: shop for shop in shops}

    def list_by_ids(self, shop_ids: list[UUID]) -> list[Shop]:
        return [self.shops[shop_id] for shop_id in shop_ids if shop_id in self.shops]


class FakeBindingRepository:
    def __init__(self, enabled_shop_ids: set[UUID]) -> None:
        self.enabled_shop_ids = enabled_shop_ids

    def list_enabled_shop_ids_for_device(
        self,
        device_id: UUID,
        shop_ids: list[UUID],
    ) -> set[UUID]:
        del device_id
        return set(shop_ids).intersection(self.enabled_shop_ids)


class FakeCredentialService:
    def __init__(self, unavailable_shop_id: UUID | None = None) -> None:
        self.unavailable_shop_id = unavailable_shop_id
        self.checked: list[UUID] = []

    def ensure_task_accounts_available(self, shop_ids: list[UUID]) -> None:
        self.checked = list(shop_ids)
        if self.unavailable_shop_id in shop_ids:
            raise CredentialNotFoundError(
                details={"shop_id": str(self.unavailable_shop_id)},
            )


def make_shop(*, enabled: bool = True) -> Shop:
    return Shop(
        shop_id=uuid4(),
        display_name="多店铺测试",
        platform=ShopPlatform.DOUYIN,
        enabled=enabled,
    )


def make_service(
    shops: list[Shop],
    *,
    bound_shop_ids: set[UUID] | None = None,
    unavailable_credential_shop_id: UUID | None = None,
) -> tuple[TaskService, FakeTaskRepository, FakeCredentialService, Device]:
    device = Device(device_id=uuid4(), display_name="多店铺设备", enabled=True)
    task_repository = FakeTaskRepository(device)
    credential_service = FakeCredentialService(unavailable_credential_shop_id)
    return (
        TaskService(
            FakeSession(),  # type: ignore[arg-type]
            task_repository,  # type: ignore[arg-type]
            credential_service=credential_service,  # type: ignore[arg-type]
            shop_repository=FakeShopRepository(shops),  # type: ignore[arg-type]
            shop_device_binding_repository=FakeBindingRepository(
                bound_shop_ids
                if bound_shop_ids is not None
                else {shop.shop_id for shop in shops},
            ),  # type: ignore[arg-type]
        ),
        task_repository,
        credential_service,
        device,
    )


def request(device_id: UUID, shop_ids: list[UUID]) -> TaskCreate:
    return TaskCreate(
        target_device_id=device_id,
        shop_ids=shop_ids,
        skill_id=TaskSkillId.SYSTEM_ECHO,
        input={"message": "multi-shop"},
    )


def test_five_shops_create_one_task_and_preserve_user_order() -> None:
    shops = [make_shop() for _ in range(5)]
    service, repository, credentials, device = make_service(shops)
    ordered_shop_ids = [shop.shop_id for shop in reversed(shops)]

    task = service.create(request(device.device_id, ordered_shop_ids), ACTOR)

    assert repository.tasks == [task]
    assert task.shop_ids == ordered_shop_ids
    assert [link.position for link in task.shop_links] == list(range(5))
    assert credentials.checked == ordered_shop_ids


def test_duplicate_shop_ids_are_rejected_by_the_create_contract() -> None:
    shop_id = uuid4()
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        request(uuid4(), [shop_id, shop_id])


@pytest.mark.parametrize("missing", [True, False])
def test_missing_or_disabled_shop_rejects_the_whole_task(missing: bool) -> None:
    valid = make_shop()
    invalid = make_shop(enabled=False)
    shops = [valid] if missing else [valid, invalid]
    invalid_id = uuid4() if missing else invalid.shop_id
    service, repository, _, device = make_service(shops)

    with pytest.raises(TaskShopInvalidError) as captured:
        service.create(request(device.device_id, [valid.shop_id, invalid_id]), ACTOR)

    assert repository.tasks == []
    assert captured.value.details == {"shop_ids": [str(invalid_id)]}


def test_one_unbound_shop_rejects_the_whole_task() -> None:
    first, second = make_shop(), make_shop()
    service, repository, _, device = make_service(
        [first, second],
        bound_shop_ids={first.shop_id},
    )

    with pytest.raises(TaskShopDeviceBindingInvalidError) as captured:
        service.create(request(device.device_id, [first.shop_id, second.shop_id]), ACTOR)

    assert repository.tasks == []
    assert captured.value.details == {"shop_ids": [str(second.shop_id)]}


def test_one_missing_credential_rejects_the_whole_task() -> None:
    first, second = make_shop(), make_shop()
    service, repository, _, device = make_service(
        [first, second],
        unavailable_credential_shop_id=second.shop_id,
    )

    with pytest.raises(CredentialNotFoundError):
        service.create(request(device.device_id, [first.shop_id, second.shop_id]), ACTOR)

    assert repository.tasks == []
