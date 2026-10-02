from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.exceptions import SuperAccountRequiredError
from app.modules.access.repository import TeamResourceAccessRepository
from app.modules.devices.exceptions import DeviceNotFoundError
from app.modules.devices.repository import DeviceRepository
from app.modules.operating_dashboard.service import OperatingDashboardService
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.exceptions import (
    ImmutableShopIdentityError,
    InvalidDeviceBindingError,
    OperatingStartDateConflictError,
    ShopNotFoundError,
)
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
        resource_access_repository: TeamResourceAccessRepository | None = None,
    ) -> None:
        self.session = session
        self.shop_repository = shop_repository or ShopRepository(session)
        self.binding_repository = binding_repository or ShopDeviceBindingRepository(session)
        self.device_repository = device_repository or DeviceRepository(session)
        self.user_repository = user_repository or UserRepository(session)
        self.resource_access_repository = (
            resource_access_repository or TeamResourceAccessRepository(session)
        )

    def list(
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
    ) -> tuple[list[Shop], int, dict[UUID, ShopSessionStatus]]:
        shops = self.shop_repository.list_for_actor(
            actor=actor,
            offset=offset,
            limit=limit,
            device_id=device_id,
            enabled=enabled,
            owner_user_id=owner_user_id,
            platform=platform,
            name_query=name_query,
        )
        return (
            shops,
            self.shop_repository.count_for_actor(
                actor=actor,
                device_id=device_id,
                enabled=enabled,
                owner_user_id=owner_user_id,
                platform=platform,
                name_query=name_query,
            ),
            self.shop_repository.list_session_statuses(
                [shop.shop_id for shop in shops],
            ),
        )

    def get(self, actor: ActorContext, shop_id: UUID) -> Shop:
        shop = self.shop_repository.get_for_actor(actor=actor, shop_id=shop_id)
        if shop is None:
            raise ShopNotFoundError()
        return shop

    def _ensure_owner_exists(self, owner_user_id: UUID | None) -> None:
        if owner_user_id is not None and self.user_repository.get(owner_user_id) is None:
            raise UserNotFoundError()

    def create(self, actor: ActorContext, data: ShopCreate) -> Shop:
        self._require_super_account(actor)
        team_id = actor.require_team_id()
        self._ensure_owner_exists(data.owner_user_id)
        shop = Shop(**data.model_dump())
        self.shop_repository.add(shop)
        self.session.flush()
        self.resource_access_repository.replace_shop_ids(
            team_id,
            [
                *self.resource_access_repository.list_shop_ids(team_id),
                shop.shop_id,
            ],
        )
        self.session.commit()
        self.session.refresh(shop)
        return shop

    def update(self, actor: ActorContext, shop_id: UUID, data: ShopUpdate) -> Shop:
        self._require_super_account(actor)
        shop = self.shop_repository.get_for_update(shop_id)
        if shop is None:
            raise ShopNotFoundError()
        changes = data.model_dump(exclude_unset=True)
        previous_operating_start_date = shop.operating_start_date
        operating_start_date_changed = "operating_start_date" in changes
        requested_operating_start_date = changes.pop(
            "operating_start_date",
            None,
        )
        operating_start_date_effectively_changed = (
            operating_start_date_changed
            and requested_operating_start_date != previous_operating_start_date
        )
        dashboard_service = OperatingDashboardService(self.session)
        if (
            operating_start_date_effectively_changed
            and requested_operating_start_date is not None
            and dashboard_service.has_confirmed_metric_before(
                shop_id=shop.shop_id,
                operating_start_date=requested_operating_start_date,
            )
        ):
            # ``get_for_update`` deliberately holds a row lock.  Release it
            # before exposing the conflict so a rejected edit cannot block
            # ordinary Shop/session work in the same request process.
            self.session.rollback()
            raise OperatingStartDateConflictError()
        if shop.platform_shop_id is not None and {
            "display_name",
            "platform",
        }.intersection(changes):
            raise ImmutableShopIdentityError()
        if "owner_user_id" in changes:
            self._ensure_owner_exists(changes["owner_user_id"])
        for field, value in changes.items():
            setattr(shop, field, value)
        if operating_start_date_effectively_changed:
            if requested_operating_start_date is None:
                shop.operating_start_date = None
                shop.operating_start_date_source = None
                shop.operating_start_date_set_by_user_id = None
                shop.operating_start_date_set_at = None
            else:
                shop.operating_start_date = requested_operating_start_date
                shop.operating_start_date_source = "manual"
                shop.operating_start_date_set_by_user_id = actor.user_id
                shop.operating_start_date_set_at = datetime.now(UTC)
            # Make the changed boundary visible to the queue's set-based
            # cleanup in this same database transaction.  Facts are never
            # altered; only unstarted requests outside the new scope stop.
            self.session.flush()
            dashboard_service.skip_not_operating_collection_items(
                shop_id=shop.shop_id,
                now=datetime.now(UTC),
            )

        self.session.commit()
        self.session.refresh(shop)
        return shop

    def remove(self, actor: ActorContext, shop_id: UUID) -> None:
        self._require_super_account(actor)
        shop = self.shop_repository.get_for_update(shop_id)
        if shop is None:
            raise ShopNotFoundError()
        shop.enabled = False
        shop.deleted_at = datetime.now(UTC)
        self.binding_repository.disable_enabled_by_shop(shop_id)
        self.session.commit()

    def list_bindings(
        self,
        actor: ActorContext,
        shop_id: UUID,
    ) -> list[ShopDeviceBinding]:
        self.get(actor, shop_id)
        return self.binding_repository.list_by_shop(shop_id)

    def _ensure_device_exists(self, device_id: UUID) -> None:
        if self.device_repository.get(device_id) is None:
            raise DeviceNotFoundError()

    def create_binding(
        self,
        actor: ActorContext,
        shop_id: UUID,
        data: ShopDeviceBindingCreate,
    ) -> ShopDeviceBinding:
        self._require_super_account(actor)
        if self.shop_repository.get(shop_id) is None:
            raise ShopNotFoundError()
        self._ensure_device_exists(data.device_id)
        if self.binding_repository.get(shop_id, data.device_id) is not None:
            raise InvalidDeviceBindingError("该店铺与设备已经存在绑定关系")
        binding = ShopDeviceBinding(shop_id=shop_id, **data.model_dump())
        self.binding_repository.add(binding)
        return self._commit_binding(binding)

    def update_binding(
        self,
        actor: ActorContext,
        shop_id: UUID,
        device_id: UUID,
        data: ShopDeviceBindingUpdate,
    ) -> ShopDeviceBinding:
        self._require_super_account(actor)
        if self.shop_repository.get(shop_id) is None:
            raise ShopNotFoundError()
        binding = self.binding_repository.get(shop_id, device_id)
        if binding is None:
            raise InvalidDeviceBindingError("设备绑定关系不存在")
        changes = data.model_dump(exclude_unset=True)
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

    @staticmethod
    def _require_super_account(actor: ActorContext) -> None:
        if not actor.is_super_account:
            raise SuperAccountRequiredError()
