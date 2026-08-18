from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.config import Settings
from app.main import create_app
from app.modules.devices.models import Device
from app.modules.tasks.enums import TaskSkillId
from app.modules.tasks.skill_contracts import validate_skill_input
from app.modules.workers.models import DeviceRuntime, WorkerDeviceCredential
from app.modules.workers.schemas import WorkerHeartbeat
from app.modules.workers.security import hash_worker_token, verify_worker_token
from app.modules.workers.service import WorkerPrincipal, WorkerService
from tests.support import FakeSession


class FakeWorkerRepository:
    def __init__(self, device: Device) -> None:
        self.device = device
        self.credential: WorkerDeviceCredential | None = None
        self.runtime: DeviceRuntime | None = None

    def get_device(self, device_id: object) -> Device | None:
        return self.device if device_id == self.device.device_id else None

    def get_credential(self, device_id: object) -> WorkerDeviceCredential | None:
        return self.credential if device_id == self.device.device_id else None

    def add_credential(self, credential: WorkerDeviceCredential) -> None:
        self.credential = credential

    def upsert_runtime(
        self,
        *,
        device_id: object,
        worker_version: str,
        last_seen_at: datetime,
        started_at: datetime,
    ) -> DeviceRuntime:
        self.runtime = DeviceRuntime(
            device_id=device_id,
            worker_version=worker_version,
            last_seen_at=last_seen_at,
            started_at=started_at,
        )
        self.runtime.created_at = last_seen_at
        self.runtime.updated_at = last_seen_at
        return self.runtime

    def get_runtimes(self, device_ids: object) -> dict[object, DeviceRuntime]:
        if self.runtime is None:
            return {}
        return {self.runtime.device_id: self.runtime}


def test_worker_token_is_hashed_and_runtime_online_is_time_based() -> None:
    device = Device(device_id=uuid4(), display_name="Worker PC", enabled=True)
    repository = FakeWorkerRepository(device)
    session = FakeSession()
    settings = Settings(worker_online_timeout_seconds=45)
    service = WorkerService(session, repository, settings)  # type: ignore[arg-type]

    token = service.issue_token(device.device_id)
    assert repository.credential is not None
    assert repository.credential.token_hash != token
    assert len(repository.credential.token_hash) == 64
    assert service.authenticate(device.device_id, token) == WorkerPrincipal(
        device_id=device.device_id,
    )

    now = datetime.now(UTC)
    runtime = service.heartbeat(
        WorkerPrincipal(device_id=device.device_id),
        WorkerHeartbeat(worker_version="0.1.0", started_at=now),
        now=now,
    )
    assert runtime.connection_status == "online"
    assert service.to_runtime_read(
        repository.runtime,  # type: ignore[arg-type]
        now=now + timedelta(seconds=46),
    ).connection_status == "offline"


def test_worker_token_hash_and_skill_contracts() -> None:
    token = "ccw_example-secret"
    digest = hash_worker_token(token)
    assert token not in digest
    assert verify_worker_token(token, digest)
    assert not verify_worker_token("ccw_wrong", digest)
    assert validate_skill_input(
        TaskSkillId.SYSTEM_ECHO,
        {"message": "hello"},
    ) == {"message": "hello"}
    assert validate_skill_input(
        TaskSkillId.SYSTEM_SLEEP,
        {"seconds": 45},
    ) == {"seconds": 45.0}


def test_openapi_exposes_only_whitelisted_worker_task_operations() -> None:
    paths = create_app().openapi()["paths"]
    expected = {
        "/api/v1/tasks",
        "/api/v1/tasks/{task_id}",
        "/api/v1/worker/heartbeat",
        "/api/v1/worker/tasks/claim",
        "/api/v1/worker/tasks/{task_id}/renew",
        "/api/v1/worker/tasks/{task_id}/complete",
        "/api/v1/worker/tasks/{task_id}/fail",
    }
    assert expected <= set(paths)
    assert all("command" not in path for path in paths)
