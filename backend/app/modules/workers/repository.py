from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.devices.models import Device
from app.modules.workers.models import DeviceRuntime, WorkerDeviceCredential


class WorkerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_device(self, device_id: UUID) -> Device | None:
        return self.session.get(Device, device_id)

    def get_credential(self, device_id: UUID) -> WorkerDeviceCredential | None:
        statement = select(WorkerDeviceCredential).where(
            WorkerDeviceCredential.device_id == device_id,
        )
        return self.session.scalar(statement)

    def add_credential(self, credential: WorkerDeviceCredential) -> None:
        self.session.add(credential)

    def upsert_runtime(
        self,
        *,
        device_id: UUID,
        worker_version: str,
        last_seen_at: datetime,
        started_at: datetime,
    ) -> DeviceRuntime:
        statement = (
            insert(DeviceRuntime)
            .values(
                device_id=device_id,
                worker_version=worker_version,
                last_seen_at=last_seen_at,
                started_at=started_at,
                updated_at=last_seen_at,
            )
            .on_conflict_do_update(
                index_elements=[DeviceRuntime.device_id],
                set_={
                    "worker_version": worker_version,
                    "last_seen_at": last_seen_at,
                    "started_at": started_at,
                    "updated_at": last_seen_at,
                },
            )
            .returning(DeviceRuntime)
            .execution_options(populate_existing=True)
        )
        return self.session.execute(statement).scalar_one()

    def get_runtime(self, device_id: UUID) -> DeviceRuntime | None:
        return self.session.get(DeviceRuntime, device_id)

    def get_runtimes(self, device_ids: Iterable[UUID]) -> dict[UUID, DeviceRuntime]:
        identifiers = list(device_ids)
        if not identifiers:
            return {}
        statement = select(DeviceRuntime).where(DeviceRuntime.device_id.in_(identifiers))
        return {runtime.device_id: runtime for runtime in self.session.scalars(statement)}
