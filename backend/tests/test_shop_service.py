from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.devices.exceptions import DeviceNotFoundError
from app.modules.devices.models import Device
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.shops.enums import ShopPlatform
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
        self.session_statuses: dict[UUID, ShopSessionStatus] = {}

    def list(
        self,
        *,
        offset: int,
        limit: int,
        device_id: UUID | None = None,
        enabled: bool | None = None,
    ) -> list[Shop]:
        active = [shop for shop in self.items.values() if shop.deleted_at is None]
        if enabled is not None:
            active = [shop for shop in active if shop.enabled is enabled]
        del device_id
        return active[offset : offset + limit]

    def count(
        self,
        *,
        device_id: UUID | None = None,
        enabled: bool | None = None,
    ) -> int:
        del device_id
        return sum(
            shop.deleted_at is None
            and (enabled is None or shop.enabled is enabled)
            for shop in self.items.values()
        )

    def get(self, shop_id: UUID) -> Shop | None:
        shop = self.items.get(shop_id)
        return shop if shop is not None and shop.deleted_at is None else None

    def get_including_deleted(self, shop_id: UUID) -> Shop | None:
        return self.items.get(shop_id)

    def list_session_statuses(
        self,
        shop_ids: list[UUID],
    ) -> dict[UUID, ShopSessionStatus]:
        return {
            shop_id: self.session_statuses[shop_id]
            for shop_id in shop_ids
            if shop_id in self.session_statuses
        }

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

    def add(self, binding: ShopDeviceBinding) -> None:
        self.items[(binding.shop_id, binding.device_id)] = binding

    def disable_enabled_by_shop(self, shop_id: UUID) -> int:
        changed = 0
        for binding in self.list_by_shop(shop_id):
            if binding.enabled:
                binding.enabled = False
                changed += 1
        return changed


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
    items, total, session_statuses = service.list(offset=0, limit=20)
    updated = service.update(
        created.shop_id,
        ShopUpdate(display_name="正式店铺 A", enabled=False),
    )

    assert fetched is created
    assert items == [created]
    assert total == 1
    assert session_statuses == {}
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


def test_binding_many_to_many_duplicate_and_disable() -> None:
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

    first = service.create_binding(
        shop.shop_id,
        ShopDeviceBindingCreate(device_id=primary_device_id),
    )
    second = service.create_binding(
        shop.shop_id,
        ShopDeviceBindingCreate(device_id=backup_device_id),
    )

    with pytest.raises(InvalidDeviceBindingError):
        service.create_binding(
            shop.shop_id,
            ShopDeviceBindingCreate(device_id=primary_device_id),
        )

    disabled = service.update_binding(
        shop.shop_id,
        primary_device_id,
        ShopDeviceBindingUpdate(enabled=False),
    )
    unchanged_second = service.update_binding(
        shop.shop_id,
        backup_device_id,
        ShopDeviceBindingUpdate(enabled=True),
    )

    assert first.device_id == primary_device_id
    assert second.device_id == backup_device_id
    assert disabled.enabled is False
    assert unchanged_second.enabled is True
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
            ShopDeviceBindingCreate(device_id=uuid4()),
        )
    with pytest.raises(InvalidDeviceBindingError):
        service.update_binding(
            shop.shop_id,
            uuid4(),
            ShopDeviceBindingUpdate(enabled=False),
        )


def test_list_projects_real_session_status() -> None:
    service, _, shops, _, user_id, _ = build_service()
    shop = service.create(
        ShopCreate(
            display_name="Session 状态店铺",
            platform=ShopPlatform.DOUYIN,
            owner_user_id=user_id,
        ),
    )
    shops.session_statuses[shop.shop_id] = ShopSessionStatus.CAPTURED

    items, total, session_statuses = service.list(offset=0, limit=20)

    assert items == [shop]
    assert total == 1
    assert session_statuses == {shop.shop_id: ShopSessionStatus.CAPTURED}


def test_soft_remove_excludes_shop_and_disables_bindings() -> None:
    service, session, shops, bindings, user_id, device_id = build_service()
    shop = service.create(
        ShopCreate(
            display_name="软删除测试店铺",
            platform=ShopPlatform.DOUYIN,
            owner_user_id=user_id,
        ),
    )
    service.create_binding(
        shop.shop_id,
        ShopDeviceBindingCreate(device_id=device_id),
    )

    service.remove(shop.shop_id)

    stored = shops.get_including_deleted(shop.shop_id)
    assert stored is shop
    assert stored.enabled is False
    assert isinstance(stored.deleted_at, datetime)
    assert stored.deleted_at.tzinfo is UTC
    assert bindings.get(shop.shop_id, device_id).enabled is False  # type: ignore[union-attr]
    assert service.list(offset=0, limit=20) == ([], 0, {})
    with pytest.raises(ShopNotFoundError):
        service.get(shop.shop_id)
    assert session.commits == 3
