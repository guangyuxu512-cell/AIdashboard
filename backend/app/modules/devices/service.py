from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.devices.exceptions import (
    DeviceHasActiveTasksError,
    DeviceNotFoundError,
)
from app.modules.devices.models import Device
from app.modules.devices.repository import DeviceRepository
from app.modules.devices.schemas import DeviceCreate, DeviceUpdate
from app.modules.shops.repository import ShopDeviceBindingRepository
from app.modules.tasks.repository import TaskRepository
from app.modules.workers.repository import WorkerRepository


class DeviceService:
    def __init__(
        self,
        session: Session,
        repository: DeviceRepository | None = None,
        binding_repository: ShopDeviceBindingRepository | None = None,
        task_repository: TaskRepository | None = None,
        worker_repository: WorkerRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or DeviceRepository(session)
        self.binding_repository = binding_repository or ShopDeviceBindingRepository(
            session,
        )
        self.task_repository = task_repository or TaskRepository(session)
        self.worker_repository = worker_repository or WorkerRepository(session)

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

    def remove(self, device_id: UUID) -> None:
        device = self.repository.get_for_update(device_id)
        if device is None:
            raise DeviceNotFoundError()
        if self.task_repository.has_active_for_device(device_id):
            self.session.rollback()
            raise DeviceHasActiveTasksError()

        device.enabled = False
        device.deleted_at = datetime.now(UTC)
        self.binding_repository.disable_enabled_by_device(device_id)
        self.worker_repository.disable_credentials_by_device(device_id)
        self.session.commit()
