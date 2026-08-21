from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.modules.shops.enums import BindingRole, ShopPlatform
from app.modules.shops.models import Shop, ShopDeviceBinding
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.models import ShopSession


class ShopRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, *, offset: int, limit: int) -> list[Shop]:
        statement = (
            select(Shop)
            .where(Shop.deleted_at.is_(None))
            .order_by(Shop.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def count(self) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(Shop)
                .where(Shop.deleted_at.is_(None)),
            )
            or 0
        )

    def get(self, shop_id: UUID) -> Shop | None:
        return self.session.scalar(
            select(Shop).where(
                Shop.shop_id == shop_id,
                Shop.deleted_at.is_(None),
            ),
        )

    def get_including_deleted(self, shop_id: UUID) -> Shop | None:
        return self.session.get(Shop, shop_id)

    def list_session_statuses(
        self,
        shop_ids: list[UUID],
    ) -> dict[UUID, ShopSessionStatus]:
        if not shop_ids:
            return {}
        rows = self.session.execute(
            select(ShopSession.shop_id, ShopSession.status).where(
                ShopSession.shop_id.in_(shop_ids),
            ),
        )
        return {shop_id: status for shop_id, status in rows}

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

    def disable_enabled_by_shop(self, shop_id: UUID) -> int:
        result = self.session.execute(
            update(ShopDeviceBinding)
            .where(
                ShopDeviceBinding.shop_id == shop_id,
                ShopDeviceBinding.enabled.is_(True),
            )
            .values(enabled=False, updated_at=func.now()),
        )
        return result.rowcount

    def disable_enabled_by_device(self, device_id: UUID) -> int:
        result = self.session.execute(
            update(ShopDeviceBinding)
            .where(
                ShopDeviceBinding.device_id == device_id,
                ShopDeviceBinding.enabled.is_(True),
            )
            .values(enabled=False, updated_at=func.now()),
        )
        return result.rowcount
