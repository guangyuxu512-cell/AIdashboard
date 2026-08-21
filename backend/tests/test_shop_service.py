from uuid import UUID, uuid4

import pytest

from app.modules.devices.exceptions import DeviceNotFoundError
from app.modules.devices.models import Device
from app.modules.shops.enums import BindingRole, ShopPlatform
from app.modules.shops.exceptions import (
    ImmutableShopIdentityError,
    InvalidDeviceBindingError,
    ShopNotFoundError,
)
from app.modules.shops.models import Shop, ShopDeviceBinding
from app.modules.shops.schemas import (
    ShopCreate,
    ShopDeviceBindingCreate,
    ShopDeviceBindingUpdate,
    ShopUpdate,
)
from app.modules.shops.service import ShopService
from app.modules.users.models import User
from tests.support import FakeSession


class FakeShopRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, Shop] = {}

    def list(self, *, offset: int, limit: int) -> list[Shop]:
        return list(self.items.values())[offset : offset + limit]

    def count(self) -> int:
        return len(self.items)

    def get(self, shop_id: UUID) -> Shop | None:
        return self.items.get(shop_id)

    def add(self, shop: Shop) -> None:
        if shop.shop_id is None:
            shop.shop_id = uuid4()
        self.items[shop.shop_id] = shop


class FakeEntityRepository:
    def __init__(self, items: dict[UUID, object] | None = None) -> None:
        self.items = items or {}

    def get(self, entity_id: UUID) -> object | None:
        return self.items.get(entity_id)


class FakeBindingRepository:
    def __init__(self) -> None:
        self.items: dict[tuple[UUID, UUID], ShopDeviceBinding] = {}

    def list_by_shop(self, shop_id: UUID) -> list[ShopDeviceBinding]:
        return [binding for binding in self.items.values() if binding.shop_id == shop_id]

    def get(self, shop_id: UUID, device_id: UUID) -> ShopDeviceBinding | None:
        return self.items.get((shop_id, device_id))

    def get_enabled_primary(
        self,
        shop_id: UUID,
        *,
        excluding_device_id: UUID | None = None,
    ) -> ShopDeviceBinding | None:
        return next(
            (
                binding
                for binding in self.items.values()
                if binding.shop_id == shop_id
                and binding.device_id != excluding_device_id
                and binding.binding_role == BindingRole.PRIMARY
                and binding.enabled
            ),
            None,
        )

    def add(self, binding: ShopDeviceBinding) -> None:
        self.items[(binding.shop_id, binding.device_id)] = binding


def build_service() -> tuple[
    ShopService,
    FakeSession,
    FakeShopRepository,
    FakeBindingRepository,
    UUID,
    UUID,
]:
    session = FakeSession()
    shops = FakeShopRepository()
    bindings = FakeBindingRepository()
    user_id = uuid4()
    device_id = uuid4()
    users = FakeEntityRepository({user_id: User(user_id=user_id, display_name="负责人")})
    devices = FakeEntityRepository(
        {device_id: Device(device_id=device_id, display_name="设备 01")},
    )
    service = ShopService(
        session,  # type: ignore[arg-type]
        shops,  # type: ignore[arg-type]
        bindings,  # type: ignore[arg-type]
        devices,  # type: ignore[arg-type]
        users,  # type: ignore[arg-type]
    )
    return service, session, shops, bindings, user_id, device_id


def test_shop_create_get_list_and_update() -> None:
    service, session, _, _, user_id, _ = build_service()

    created = service.create(
        ShopCreate(
            display_name="正式店铺",
            platform=ShopPlatform.DOUYIN,
            owner_user_id=user_id,
            note="基础备注",
        ),
    )
    fetched = service.get(created.shop_id)
    items, total = service.list(offset=0, limit=20)
    updated = service.update(
        created.shop_id,
        ShopUpdate(display_name="正式店铺 A", enabled=False),
    )

    assert fetched is created
    assert items == [created]
    assert total == 1
    assert updated.display_name == "正式店铺 A"
    assert updated.enabled is False
    assert session.commits == 2


def test_shop_not_found() -> None:
    service, _, _, _, _, _ = build_service()

    with pytest.raises(ShopNotFoundError):
        service.get(uuid4())


def test_platform_identified_shop_identity_is_immutable() -> None:
    service, session, _, _, user_id, _ = build_service()
    shop = service.create(
        ShopCreate(
            display_name="平台真实店名",
            platform=ShopPlatform.DOUYIN,
            platform_shop_id="987654321",
            owner_user_id=user_id,
        ),
    )

    with pytest.raises(ImmutableShopIdentityError):
        service.update(shop.shop_id, ShopUpdate(display_name="人工改名"))
    with pytest.raises(ImmutableShopIdentityError):
        service.update(shop.shop_id, ShopUpdate(platform=ShopPlatform.PDD))

    updated = service.update(shop.shop_id, ShopUpdate(enabled=False, note="可编辑备注"))

    assert updated.display_name == "平台真实店名"
    assert updated.platform == ShopPlatform.DOUYIN
    assert updated.enabled is False
    assert updated.note == "可编辑备注"
    assert session.commits == 2


def test_binding_primary_backup_duplicate_and_disable() -> None:
    service, _, _, bindings, user_id, primary_device_id = build_service()
    shop = service.create(
        ShopCreate(
            display_name="绑定测试店铺",
            platform=ShopPlatform.PDD,
            owner_user_id=user_id,
        ),
    )
    backup_device_id = uuid4()
    service.device_repository.items[backup_device_id] = Device(  # type: ignore[attr-defined]
        device_id=backup_device_id,
        display_name="备用设备",
    )

    primary = service.create_binding(
        shop.shop_id,
        ShopDeviceBindingCreate(
            device_id=primary_device_id,
            binding_role=BindingRole.PRIMARY,
        ),
    )
    backup = service.create_binding(
        shop.shop_id,
        ShopDeviceBindingCreate(
            device_id=backup_device_id,
            binding_role=BindingRole.BACKUP,
        ),
    )

    with pytest.raises(InvalidDeviceBindingError):
        service.create_binding(
            shop.shop_id,
            ShopDeviceBindingCreate(
                device_id=primary_device_id,
                binding_role=BindingRole.PRIMARY,
            ),
        )

    with pytest.raises(InvalidDeviceBindingError):
        service.update_binding(
            shop.shop_id,
            backup_device_id,
            ShopDeviceBindingUpdate(binding_role=BindingRole.PRIMARY),
        )

    disabled = service.update_binding(
        shop.shop_id,
        primary_device_id,
        ShopDeviceBindingUpdate(enabled=False),
    )
    promoted = service.update_binding(
        shop.shop_id,
        backup_device_id,
        ShopDeviceBindingUpdate(binding_role=BindingRole.PRIMARY),
    )

    assert primary.binding_role == BindingRole.PRIMARY
    assert disabled.enabled is False
    assert promoted.binding_role == BindingRole.PRIMARY
    assert len(bindings.items) == 2


def test_binding_rejects_unknown_device_and_missing_relation() -> None:
    service, _, _, _, user_id, _ = build_service()
    shop = service.create(
        ShopCreate(
            display_name="非法关系测试店铺",
            platform=ShopPlatform.DOUYIN,
            owner_user_id=user_id,
        ),
    )

    with pytest.raises(DeviceNotFoundError):
        service.create_binding(
            shop.shop_id,
            ShopDeviceBindingCreate(
                device_id=uuid4(),
                binding_role=BindingRole.BACKUP,
            ),
        )
    with pytest.raises(InvalidDeviceBindingError):
        service.update_binding(
            shop.shop_id,
            uuid4(),
            ShopDeviceBindingUpdate(enabled=False),
        )
