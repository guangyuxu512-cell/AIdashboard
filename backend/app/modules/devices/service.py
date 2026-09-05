from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
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

    def list(
        self,
        *,
        actor: ActorContext,
        offset: int,
        limit: int,
    ) -> tuple[list[Device], int]:
        return (
            self.repository.list(actor=actor, offset=offset, limit=limit),
            self.repository.count(actor=actor),
        )

    def get(self, actor: ActorContext, device_id: UUID) -> Device:
        device = self.repository.get_for_actor(actor=actor, device_id=device_id)
        if device is None:
            raise DeviceNotFoundError()
        return device

    def get_for_write(self, actor: ActorContext, device_id: UUID) -> Device:
        device = self.repository.get_for_actor_for_update(
            actor=actor,
            device_id=device_id,
        )
        if device is None or device.team_id != actor.team_id:
            raise DeviceNotFoundError()
        return device

    def create(self, actor: ActorContext, data: DeviceCreate) -> Device:
        device = Device(
            **data.model_dump(),
            team_id=actor.team_id,
            created_by_user_id=actor.user_id,
        )
        self.repository.add(device)
        self.session.commit()
        self.session.refresh(device)
        return device

    def update(
        self,
        actor: ActorContext,
        device_id: UUID,
        data: DeviceUpdate,
    ) -> Device:
        device = self.get_for_write(actor, device_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(device, field, value)
        self.session.commit()
        self.session.refresh(device)
        return device

    def remove(self, actor: ActorContext, device_id: UUID) -> None:
        device = self.get_for_write(actor, device_id)
        if self.task_repository.has_active_for_device(device_id):
            self.session.rollback()
            raise DeviceHasActiveTasksError()

        device.enabled = False
        device.deleted_at = datetime.now(UTC)
        self.binding_repository.disable_enabled_by_device(device_id)
        self.worker_repository.disable_credentials_by_device(device_id)
        self.session.commit()
