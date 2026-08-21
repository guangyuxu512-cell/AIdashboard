from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.devices.models import Device


class DeviceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, *, offset: int, limit: int) -> list[Device]:
        statement = (
            select(Device)
            .where(Device.deleted_at.is_(None))
            .order_by(Device.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def count(self) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(Device)
                .where(Device.deleted_at.is_(None)),
            )
            or 0
        )

    def get(self, device_id: UUID) -> Device | None:
        return self.session.scalar(
            select(Device).where(
                Device.device_id == device_id,
                Device.deleted_at.is_(None),
            ),
        )

    def get_for_update(self, device_id: UUID) -> Device | None:
        return self.session.scalar(
            select(Device)
            .where(
                Device.device_id == device_id,
                Device.deleted_at.is_(None),
            )
            .with_for_update(),
        )

    def get_including_deleted(self, device_id: UUID) -> Device | None:
        return self.session.get(Device, device_id)

    def add(self, device: Device) -> None:
        self.session.add(device)
