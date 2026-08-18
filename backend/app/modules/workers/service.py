from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.devices.exceptions import DeviceNotFoundError
from app.modules.workers.enums import WorkerConnectionStatus
from app.modules.workers.exceptions import (
    WorkerAuthenticationError,
    WorkerCredentialNotFoundError,
)
from app.modules.workers.models import DeviceRuntime, WorkerDeviceCredential
from app.modules.workers.repository import WorkerRepository
from app.modules.workers.schemas import DeviceRuntimeRead, WorkerHeartbeat
from app.modules.workers.security import (
    generate_worker_token,
    hash_worker_token,
    verify_worker_token,
)


@dataclass(frozen=True)
class WorkerPrincipal:
    device_id: UUID


class WorkerService:
    def __init__(
        self,
        session: Session,
        repository: WorkerRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or WorkerRepository(session)
        self.settings = settings or get_settings()

    def issue_token(self, device_id: UUID) -> str:
        device = self.repository.get_device(device_id)
        if device is None:
            raise DeviceNotFoundError()
        token = generate_worker_token()
        token_hash = hash_worker_token(token)
        credential = self.repository.get_credential(device_id)
        if credential is None:
            credential = WorkerDeviceCredential(
                device_id=device_id,
                token_hash=token_hash,
                enabled=True,
            )
            self.repository.add_credential(credential)
        else:
            credential.token_hash = token_hash
            credential.enabled = True
        self.session.commit()
        return token

    def disable_token(self, device_id: UUID) -> None:
        credential = self.repository.get_credential(device_id)
        if credential is None:
            raise WorkerCredentialNotFoundError()
        credential.enabled = False
        self.session.commit()

    def authenticate(self, device_id: UUID, token: str) -> WorkerPrincipal:
        device = self.repository.get_device(device_id)
        credential = self.repository.get_credential(device_id)
        if (
            device is None
            or not device.enabled
            or credential is None
            or not credential.enabled
            or not verify_worker_token(token, credential.token_hash)
        ):
            raise WorkerAuthenticationError()
        return WorkerPrincipal(device_id=device_id)

    def heartbeat(
        self,
        principal: WorkerPrincipal,
        data: WorkerHeartbeat,
        *,
        now: datetime | None = None,
    ) -> DeviceRuntimeRead:
        seen_at = now or datetime.now(UTC)
        runtime = self.repository.upsert_runtime(
            device_id=principal.device_id,
            worker_version=data.worker_version,
            last_seen_at=seen_at,
            started_at=data.started_at,
        )
        self.session.commit()
        return self.to_runtime_read(runtime, now=seen_at)

    def get_runtime_reads(
        self,
        device_ids: list[UUID],
        *,
        now: datetime | None = None,
    ) -> dict[UUID, DeviceRuntimeRead]:
        observed_at = now or datetime.now(UTC)
        return {
            device_id: self.to_runtime_read(runtime, now=observed_at)
            for device_id, runtime in self.repository.get_runtimes(device_ids).items()
        }

    def to_runtime_read(
        self,
        runtime: DeviceRuntime,
        *,
        now: datetime,
    ) -> DeviceRuntimeRead:
        threshold = timedelta(seconds=self.settings.worker_online_timeout_seconds)
        connection_status = (
            WorkerConnectionStatus.ONLINE
            if now - runtime.last_seen_at <= threshold
            else WorkerConnectionStatus.OFFLINE
        )
        return DeviceRuntimeRead(
            device_id=runtime.device_id,
            worker_version=runtime.worker_version,
            connection_status=connection_status,
            last_seen_at=runtime.last_seen_at,
            started_at=runtime.started_at,
            updated_at=runtime.updated_at,
        )
