from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.devices.exceptions import DeviceNotFoundError
from app.modules.devices.models import Device
from app.modules.devices.repository import DeviceRepository
from app.modules.devices.schemas import DeviceCreate, DeviceUpdate


class DeviceService:
    def __init__(
        self,
        session: Session,
        repository: DeviceRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or DeviceRepository(session)

    def list(self, *, offset: int, limit: int) -> tuple[list[Device], int]:
        return self.repository.list(offset=offset, limit=limit), self.repository.count()

    def get(self, device_id: UUID) -> Device:
        device = self.repository.get(device_id)
        if device is None:
            raise DeviceNotFoundError()
        return device

    def create(self, data: DeviceCreate) -> Device:
        device = Device(**data.model_dump())
        self.repository.add(device)
        self.session.commit()
        self.session.refresh(device)
        return device

    def update(self, device_id: UUID, data: DeviceUpdate) -> Device:
        device = self.get(device_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(device, field, value)
        self.session.commit()
        self.session.refresh(device)
        return device
