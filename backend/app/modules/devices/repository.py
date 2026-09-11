from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.policy import DataScopePolicy
from app.modules.devices.models import Device


class DeviceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(
        self,
        *,
        actor: ActorContext,
        offset: int,
        limit: int,
    ) -> list[Device]:
        statement = DataScopePolicy.apply(
            select(Device).where(Device.deleted_at.is_(None)),
            team_id_column=Device.team_id,
            created_by_user_id_column=Device.created_by_user_id,
            actor=actor,
        )
        return list(
            self.session.scalars(
                statement
            .order_by(Device.created_at.desc())
            .offset(offset)
                .limit(limit),
            ),
        )

    def count(self, *, actor: ActorContext) -> int:
        statement = DataScopePolicy.apply(
            select(func.count())
            .select_from(Device)
            .where(Device.deleted_at.is_(None)),
            team_id_column=Device.team_id,
            created_by_user_id_column=Device.created_by_user_id,
            actor=actor,
        )
        return (
            self.session.scalar(statement)
            or 0
        )

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
        statement = DataScopePolicy.apply(
            select(Device).where(
                Device.device_id == device_id,
                Device.deleted_at.is_(None),
            ),
            team_id_column=Device.team_id,
            created_by_user_id_column=Device.created_by_user_id,
            actor=actor,
        )
        return self.session.scalar(statement)

    def get_for_actor_for_update(
        self,
        *,
        actor: ActorContext,
        device_id: UUID,
    ) -> Device | None:
        statement = DataScopePolicy.apply(
            select(Device)
            .where(
                Device.device_id == device_id,
                Device.deleted_at.is_(None),
            ),
            team_id_column=Device.team_id,
            created_by_user_id_column=Device.created_by_user_id,
            actor=actor,
        )
        return self.session.scalar(statement.with_for_update())

    def get_including_deleted(self, device_id: UUID) -> Device | None:
        return self.session.get(Device, device_id)

    def add(self, device: Device) -> None:
        self.session.add(device)
