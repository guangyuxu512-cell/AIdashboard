from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.devices.models import Device


class DeviceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, *, offset: int, limit: int) -> list[Device]:
        statement = select(Device).order_by(Device.created_at.desc()).offset(offset).limit(limit)
        return list(self.session.scalars(statement))

    def count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(Device)) or 0

    def get(self, device_id: UUID) -> Device | None:
        return self.session.get(Device, device_id)

    def add(self, device: Device) -> None:
        self.session.add(device)
