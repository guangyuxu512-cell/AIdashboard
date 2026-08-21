from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.shops.enums import BindingRole, ShopPlatform
from app.modules.shops.models import Shop, ShopDeviceBinding


class ShopRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, *, offset: int, limit: int) -> list[Shop]:
        statement = select(Shop).order_by(Shop.created_at.desc()).offset(offset).limit(limit)
        return list(self.session.scalars(statement))

    def count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(Shop)) or 0

    def get(self, shop_id: UUID) -> Shop | None:
        return self.session.get(Shop, shop_id)

    def get_by_platform_identity(
        self,
        platform: ShopPlatform,
        platform_shop_id: str,
    ) -> Shop | None:
        return self.session.scalar(
            select(Shop).where(
                Shop.platform == platform,
                Shop.platform_shop_id == platform_shop_id,
            ),
        )

    def add(self, shop: Shop) -> None:
        self.session.add(shop)


class ShopDeviceBindingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_shop(self, shop_id: UUID) -> list[ShopDeviceBinding]:
        statement = (
            select(ShopDeviceBinding)
            .where(ShopDeviceBinding.shop_id == shop_id)
            .order_by(ShopDeviceBinding.created_at.asc())
        )
        return list(self.session.scalars(statement))

    def get(self, shop_id: UUID, device_id: UUID) -> ShopDeviceBinding | None:
        return self.session.get(ShopDeviceBinding, (shop_id, device_id))

    def get_enabled_primary(
        self,
        shop_id: UUID,
        *,
        excluding_device_id: UUID | None = None,
    ) -> ShopDeviceBinding | None:
        statement = select(ShopDeviceBinding).where(
            ShopDeviceBinding.shop_id == shop_id,
            ShopDeviceBinding.binding_role == BindingRole.PRIMARY,
            ShopDeviceBinding.enabled.is_(True),
        )
        if excluding_device_id is not None:
            statement = statement.where(ShopDeviceBinding.device_id != excluding_device_id)
        return self.session.scalar(statement)

    def add(self, binding: ShopDeviceBinding) -> None:
        self.session.add(binding)
