from __future__ import annotations

from uuid import UUID

from sqlalchemy import exists, false, func, select, update
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.models import TeamShopAccess
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop, ShopDeviceBinding
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.models import ShopSession


class ShopRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_actor(
        self,
        *,
        actor: ActorContext,
        offset: int,
        limit: int,
        device_id: UUID | None = None,
        enabled: bool | None = None,
        owner_user_id: UUID | None = None,
        platform: str | None = None,
        name_query: str | None = None,
    ) -> list[Shop]:
        filters = [Shop.deleted_at.is_(None)]
        if enabled is not None:
            filters.append(Shop.enabled.is_(enabled))
        if owner_user_id is not None:
            filters.append(Shop.owner_user_id == owner_user_id)
        if platform is not None:
            filters.append(
                Shop.platform == platform
                if platform in {item.value for item in ShopPlatform}
                else false(),
            )
        if name_query:
            filters.append(Shop.display_name.ilike(f"%{name_query}%"))
        statement = select(Shop)
        if device_id is not None:
            statement = statement.join(
                ShopDeviceBinding,
                ShopDeviceBinding.shop_id == Shop.shop_id,
            )
            filters.extend(
                [
                    ShopDeviceBinding.device_id == device_id,
                    ShopDeviceBinding.enabled.is_(True),
                ],
            )
        statement = self._apply_actor_scope(
            statement,
            actor,
        )
        statement = (
            statement
            .where(*filters)
            .order_by(Shop.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def count_for_actor(
        self,
        *,
        actor: ActorContext,
        device_id: UUID | None = None,
        enabled: bool | None = None,
        owner_user_id: UUID | None = None,
        platform: str | None = None,
        name_query: str | None = None,
    ) -> int:
        filters = [Shop.deleted_at.is_(None)]
        if enabled is not None:
            filters.append(Shop.enabled.is_(enabled))
        if owner_user_id is not None:
            filters.append(Shop.owner_user_id == owner_user_id)
        if platform is not None:
            filters.append(
                Shop.platform == platform
                if platform in {item.value for item in ShopPlatform}
                else false(),
            )
        if name_query:
            filters.append(Shop.display_name.ilike(f"%{name_query}%"))
        statement = select(func.count()).select_from(Shop)
        if device_id is not None:
            statement = statement.join(
                ShopDeviceBinding,
                ShopDeviceBinding.shop_id == Shop.shop_id,
            )
            filters.extend(
                [
                    ShopDeviceBinding.device_id == device_id,
                    ShopDeviceBinding.enabled.is_(True),
                ],
            )
        statement = self._apply_actor_scope(statement, actor)
        return (
            self.session.scalar(
                statement.where(*filters),
            )
            or 0
        )

    def list_by_ids(self, shop_ids: list[UUID]) -> list[Shop]:
        if not shop_ids:
            return []
        return list(
            self.session.scalars(
                select(Shop).where(
                    Shop.shop_id.in_(shop_ids),
                    Shop.deleted_at.is_(None),
                ),
            ),
        )

    def get(self, shop_id: UUID) -> Shop | None:
        return self.session.scalar(
            select(Shop).where(
                Shop.shop_id == shop_id,
                Shop.deleted_at.is_(None),
            ),
        )

    def get_for_actor(self, *, actor: ActorContext, shop_id: UUID) -> Shop | None:
        return self.session.scalar(
            self._apply_actor_scope(
                select(Shop).where(
                    Shop.shop_id == shop_id,
                    Shop.deleted_at.is_(None),
                ),
                actor,
            ),
        )

    def get_for_update(self, shop_id: UUID) -> Shop | None:
        return self.session.scalar(
            select(Shop)
            .where(
                Shop.shop_id == shop_id,
                Shop.deleted_at.is_(None),
            )
            .with_for_update(),
        )

    def get_for_session_read(self, shop_id: UUID) -> Shop | None:
        return self.session.scalar(
            select(Shop)
            .where(Shop.shop_id == shop_id, Shop.deleted_at.is_(None))
            .with_for_update(read=True, nowait=True)
            .execution_options(populate_existing=True),
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

    @staticmethod
    def _apply_actor_scope(statement, actor: ActorContext):
        if actor.is_super_account:
            return statement
        return statement.where(
            exists(
                select(TeamShopAccess.team_id).where(
                    TeamShopAccess.team_id == actor.require_team_id(),
                    TeamShopAccess.shop_id == Shop.shop_id,
                ),
            ),
        )


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

    def get_for_session_read(
        self, shop_id: UUID, device_id: UUID,
    ) -> ShopDeviceBinding | None:
        return self.session.scalar(
            select(ShopDeviceBinding).where(
                ShopDeviceBinding.shop_id == shop_id,
                ShopDeviceBinding.device_id == device_id,
            ).with_for_update(read=True, nowait=True)
            .execution_options(populate_existing=True),
        )

    def list_enabled_shop_ids_for_device(
        self,
        device_id: UUID,
        shop_ids: list[UUID],
    ) -> set[UUID]:
        if not shop_ids:
            return set()
        return set(
            self.session.scalars(
                select(ShopDeviceBinding.shop_id).where(
                    ShopDeviceBinding.device_id == device_id,
                    ShopDeviceBinding.shop_id.in_(shop_ids),
                    ShopDeviceBinding.enabled.is_(True),
                ),
            ),
        )

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
