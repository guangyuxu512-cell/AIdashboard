from __future__ import annotations

from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.models import TeamDeviceAccess
from app.modules.devices.models import Device
from app.modules.workers.models import DeviceProviderInventory


class DeviceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(
        self,
        *,
        actor: ActorContext,
        offset: int,
        limit: int,
        search: str | None = None,
    ) -> list[Device]:
        statement = self._apply_actor_scope(self._search_statement(search), actor)
        return list(
            self.session.scalars(
                statement
            .order_by(Device.created_at.desc())
            .offset(offset)
                .limit(limit),
            ),
        )

    def count(self, *, actor: ActorContext, search: str | None = None) -> int:
        statement = self._apply_actor_scope(self._search_statement(search), actor)
        return (
            self.session.scalar(
                statement.with_only_columns(func.count()).order_by(None),
            )
            or 0
        )

    @staticmethod
    def _search_statement(search: str | None):
        statement = select(Device).where(Device.deleted_at.is_(None))
        if not search:
            return statement
        pattern = f"%{search}%"
        matching_inventory = exists(
            select(DeviceProviderInventory.device_id).where(
                DeviceProviderInventory.device_id == Device.device_id,
                DeviceProviderInventory.provider_code == "yingdao",
                DeviceProviderInventory.account_display.ilike(pattern),
            ),
        )
        return statement.where(
            or_(
                Device.display_name.ilike(pattern),
                Device.location.ilike(pattern),
                matching_inventory,
            ),
        )

    def list_all_for_actor(self, *, actor: ActorContext) -> list[Device]:
        """Return only devices already visible to the current human actor.

        Small option/catalog read models need the complete visible set rather
        than a management-page slice.  Callers still must decide which device
        facts, if any, may be exposed in their own response contract.
        """

        statement = self._apply_actor_scope(
            select(Device).where(Device.deleted_at.is_(None)),
            actor,
        )
        return list(self.session.scalars(statement.order_by(Device.device_id.asc())))

    def get(self, device_id: UUID) -> Device | None:
        """Internal lookup for legacy services outside the Human access plane."""

        return self.session.scalar(
            select(Device).where(
                Device.device_id == device_id,
                Device.deleted_at.is_(None),
            ),
        )

    def get_for_update(self, device_id: UUID) -> Device | None:
        """Internal write lookup; Human writes use get_for_actor_for_update."""

        return self.session.scalar(
            select(Device)
            .where(
                Device.device_id == device_id,
                Device.deleted_at.is_(None),
            )
            .with_for_update(),
        )

    def get_for_actor(
        self,
        *,
        actor: ActorContext,
        device_id: UUID,
    ) -> Device | None:
        statement = self._apply_actor_scope(
            select(Device).where(
                Device.device_id == device_id,
                Device.deleted_at.is_(None),
            ),
            actor,
        )
        return self.session.scalar(statement)

    def get_for_actor_for_update(
        self,
        *,
        actor: ActorContext,
        device_id: UUID,
    ) -> Device | None:
        statement = self._apply_actor_scope(
            select(Device)
            .where(
                Device.device_id == device_id,
                Device.deleted_at.is_(None),
            ),
            actor,
        )
        return self.session.scalar(statement.with_for_update())

    def get_including_deleted(self, device_id: UUID) -> Device | None:
        return self.session.get(Device, device_id)

    def add(self, device: Device) -> None:
        self.session.add(device)

    @staticmethod
    def _apply_actor_scope(statement, actor: ActorContext):
        if actor.is_super_account:
            return statement
        return statement.where(
            exists(
                select(TeamDeviceAccess.team_id).where(
                    TeamDeviceAccess.team_id == actor.require_team_id(),
                    TeamDeviceAccess.device_id == Device.device_id,
                ),
            ),
        )
