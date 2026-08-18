from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.devices.exceptions import DeviceNotFoundError
from app.modules.devices.repository import DeviceRepository
from app.modules.shops.enums import BindingRole
from app.modules.shops.exceptions import InvalidDeviceBindingError, ShopNotFoundError
from app.modules.shops.models import Shop, ShopDeviceBinding
from app.modules.shops.repository import ShopDeviceBindingRepository, ShopRepository
from app.modules.shops.schemas import (
    ShopCreate,
    ShopDeviceBindingCreate,
    ShopDeviceBindingUpdate,
    ShopUpdate,
)
from app.modules.users.exceptions import UserNotFoundError
from app.modules.users.repository import UserRepository


class ShopService:
    def __init__(
        self,
        session: Session,
        shop_repository: ShopRepository | None = None,
        binding_repository: ShopDeviceBindingRepository | None = None,
        device_repository: DeviceRepository | None = None,
        user_repository: UserRepository | None = None,
    ) -> None:
        self.session = session
        self.shop_repository = shop_repository or ShopRepository(session)
        self.binding_repository = binding_repository or ShopDeviceBindingRepository(session)
        self.device_repository = device_repository or DeviceRepository(session)
        self.user_repository = user_repository or UserRepository(session)

    def list(self, *, offset: int, limit: int) -> tuple[list[Shop], int]:
        return (
            self.shop_repository.list(offset=offset, limit=limit),
            self.shop_repository.count(),
        )

    def get(self, shop_id: UUID) -> Shop:
        shop = self.shop_repository.get(shop_id)
        if shop is None:
            raise ShopNotFoundError()
        return shop

    def _ensure_owner_exists(self, owner_user_id: UUID | None) -> None:
        if owner_user_id is not None and self.user_repository.get(owner_user_id) is None:
            raise UserNotFoundError()

    def create(self, data: ShopCreate) -> Shop:
        self._ensure_owner_exists(data.owner_user_id)
        shop = Shop(**data.model_dump())
        self.shop_repository.add(shop)
        self.session.commit()
        self.session.refresh(shop)
        return shop

    def update(self, shop_id: UUID, data: ShopUpdate) -> Shop:
        shop = self.get(shop_id)
        changes = data.model_dump(exclude_unset=True)
        if "owner_user_id" in changes:
            self._ensure_owner_exists(changes["owner_user_id"])
        for field, value in changes.items():
            setattr(shop, field, value)
        self.session.commit()
        self.session.refresh(shop)
        return shop

    def list_bindings(self, shop_id: UUID) -> list[ShopDeviceBinding]:
        self.get(shop_id)
        return self.binding_repository.list_by_shop(shop_id)

    def _ensure_device_exists(self, device_id: UUID) -> None:
        if self.device_repository.get(device_id) is None:
            raise DeviceNotFoundError()

    def _ensure_primary_available(
        self,
        shop_id: UUID,
        *,
        device_id: UUID,
        role: BindingRole,
        enabled: bool,
    ) -> None:
        if role != BindingRole.PRIMARY or not enabled:
            return
        existing = self.binding_repository.get_enabled_primary(
            shop_id,
            excluding_device_id=device_id,
        )
        if existing is not None:
            raise InvalidDeviceBindingError("一个店铺最多只能有一个启用的主设备")

    def create_binding(
        self,
        shop_id: UUID,
        data: ShopDeviceBindingCreate,
    ) -> ShopDeviceBinding:
        self.get(shop_id)
        self._ensure_device_exists(data.device_id)
        if self.binding_repository.get(shop_id, data.device_id) is not None:
            raise InvalidDeviceBindingError("该店铺与设备已经存在绑定关系")
        self._ensure_primary_available(
            shop_id,
            device_id=data.device_id,
            role=data.binding_role,
            enabled=data.enabled,
        )
        binding = ShopDeviceBinding(shop_id=shop_id, **data.model_dump())
        self.binding_repository.add(binding)
        return self._commit_binding(binding)

    def update_binding(
        self,
        shop_id: UUID,
        device_id: UUID,
        data: ShopDeviceBindingUpdate,
    ) -> ShopDeviceBinding:
        self.get(shop_id)
        binding = self.binding_repository.get(shop_id, device_id)
        if binding is None:
            raise InvalidDeviceBindingError("设备绑定关系不存在")
        changes = data.model_dump(exclude_unset=True)
        next_role = changes.get("binding_role", binding.binding_role)
        next_enabled = changes.get("enabled", binding.enabled)
        self._ensure_primary_available(
            shop_id,
            device_id=device_id,
            role=next_role,
            enabled=next_enabled,
        )
        for field, value in changes.items():
            setattr(binding, field, value)
        return self._commit_binding(binding)

    def _commit_binding(self, binding: ShopDeviceBinding) -> ShopDeviceBinding:
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise InvalidDeviceBindingError() from error
        self.session.refresh(binding)
        return binding
