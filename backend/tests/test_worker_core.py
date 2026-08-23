from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.main import create_app
from app.modules.devices.models import Device
from app.modules.tasks.enums import TaskSkillId
from app.modules.tasks.skill_contracts import validate_skill_input
from app.modules.automation_apps.schemas import AutomationInputSchema, normalize_parameters
from app.modules.workers.models import (
    DeviceRuntime,
    DeviceSkillCapability,
    WorkerDeviceCredential,
)
from app.modules.workers.exceptions import WorkerAuthenticationError
from app.modules.workers.schemas import (
    ProviderInventoryUpsert,
    SkillCapabilitySnapshotUpsert,
    WorkerHeartbeat,
)
from app.modules.workers.security import hash_worker_token, verify_worker_token
from app.modules.workers.service import WorkerPrincipal, WorkerService
from tests.support import FakeSession


class FakeWorkerRepository:
    def __init__(self, device: Device) -> None:
        self.device = device
        self.credential: WorkerDeviceCredential | None = None
        self.runtime: DeviceRuntime | None = None
        self.skill_capabilities: dict[str, DeviceSkillCapability] = {}

    def get_device(self, device_id: object) -> Device | None:
        return (
            self.device
            if device_id == self.device.device_id and self.device.deleted_at is None
            else None
        )

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
            connection_status="online",
            offline_since=None,
        )
        self.runtime.created_at = last_seen_at
        self.runtime.updated_at = last_seen_at
        return self.runtime

    def get_runtime_for_update(self, device_id: object) -> DeviceRuntime | None:
        return self.runtime if self.runtime and self.runtime.device_id == device_id else None

    def mark_stale_online_offline(
        self,
        *,
        stale_before: datetime,
        offline_since: datetime,
    ) -> list[DeviceRuntime]:
        if (
            self.runtime is None
            or self.runtime.connection_status != "online"
            or self.runtime.last_seen_at >= stale_before
        ):
            return []
        self.runtime.connection_status = "offline"
        self.runtime.offline_since = offline_since
        return [self.runtime]

    def get_runtimes(self, device_ids: object) -> dict[object, DeviceRuntime]:
        if self.runtime is None:
            return {}
        return {self.runtime.device_id: self.runtime}

    def replace_skill_capabilities(
        self,
        *,
        device_id: object,
        skills: list[object],
        updated_at: datetime,
    ) -> list[DeviceSkillCapability]:
        self.skill_capabilities = {
            skill.skill_id: DeviceSkillCapability(
                device_id=device_id,
                skill_id=skill.skill_id,
                display_name=skill.display_name,
                runtime=skill.runtime,
                provider_code=skill.provider,
                skill_version=skill.version,
                classification=(
                    skill.classification.value
                    if skill.classification is not None
                    else None
                ),
                created_at=updated_at,
                updated_at=updated_at,
            )
            for skill in skills
        }
        return self.get_skill_capabilities(device_id)

    def get_skill_capabilities(
        self,
        device_id: object,
    ) -> list[DeviceSkillCapability]:
        return sorted(
            (
                capability
                for capability in self.skill_capabilities.values()
                if capability.device_id == device_id
            ),
            key=lambda capability: capability.skill_id,
        )


class FakeNotificationService:
    def __init__(self) -> None:
        self.offline: list[str] = []
        self.recovered: list[str] = []

    def notify_device_offline(self, *, device_name: str, **_: object) -> None:
        self.offline.append(device_name)

    def notify_device_recovered(self, *, device_name: str, **_: object) -> None:
        self.recovered.append(device_name)


class FailingNotificationService:
    def notify_device_offline(self, **_: object) -> None:
        raise RuntimeError("webhook failed")

    def notify_device_recovered(self, **_: object) -> None:
        raise RuntimeError("webhook failed")


def test_worker_token_runtime_transitions_and_disabled_heartbeat() -> None:
    device = Device(device_id=uuid4(), display_name="Worker PC", enabled=True)
    repository = FakeWorkerRepository(device)
    session = FakeSession()
    settings = Settings(worker_online_timeout_seconds=45)
    notifications = FakeNotificationService()
    service = WorkerService(  # type: ignore[arg-type]
        session,
        repository,
        settings,
        notification_service=notifications,
    )

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
    assert service.reconcile_offline_devices(now=now + timedelta(seconds=46)) == 1
    assert repository.runtime.connection_status == "offline"  # type: ignore[union-attr]
    assert notifications.offline == ["Worker PC"]
    assert service.reconcile_offline_devices(now=now + timedelta(seconds=60)) == 0
    assert notifications.offline == ["Worker PC"]

    device.enabled = False
    assert service.authenticate(device.device_id, token).device_id == device.device_id
    recovered = service.heartbeat(
        WorkerPrincipal(device_id=device.device_id),
        WorkerHeartbeat(worker_version="0.1.0", started_at=now),
        now=now + timedelta(seconds=61),
    )
    assert recovered.connection_status == "online"
    assert notifications.recovered == []

    device.deleted_at = now + timedelta(seconds=62)
    with pytest.raises(WorkerAuthenticationError) as error:
        service.authenticate(device.device_id, token)
    assert getattr(error.value, "code", None) == "WORKER_AUTHENTICATION_FAILED"


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
    assert validate_skill_input(TaskSkillId.YINGDAO_TEST, {}) == {}
    assert validate_skill_input(TaskSkillId.YINGDAO_DISCOVER, {}) == {}
    assert validate_skill_input(
        TaskSkillId.YINGDAO_APP_RUN,
        {"app_id": "app-1", "params": {"count": 2}},
    ) == {"app_id": "app-1", "params": {"count": 2}}


def test_automation_application_parameters_apply_defaults_and_validate_types() -> None:
    schema = AutomationInputSchema.model_validate(
        {
            "fields": [
                {
                    "name": "keyword",
                    "label": "关键词",
                    "type": "text",
                    "required": True,
                    "default_value": None,
                    "options": [],
                },
                {
                    "name": "mode",
                    "label": "模式",
                    "type": "select",
                    "required": False,
                    "default_value": "safe",
                    "options": ["safe", "fast"],
                },
            ],
        },
    )

    assert normalize_parameters(schema, {"keyword": "商品"}) == {
        "keyword": "商品",
        "mode": "safe",
    }
    with pytest.raises(ValueError, match="关键词"):
        normalize_parameters(schema, {})
    with pytest.raises(ValueError, match="关键词"):
        normalize_parameters(schema, {"keyword": ""})
    with pytest.raises(ValueError, match="模式"):
        normalize_parameters(schema, {"keyword": "商品", "mode": "invalid"})


def test_notification_failure_does_not_rollback_runtime_transition() -> None:
    device = Device(device_id=uuid4(), display_name="Worker PC", enabled=True)
    repository = FakeWorkerRepository(device)
    session = FakeSession()
    service = WorkerService(  # type: ignore[arg-type]
        session,
        repository,
        Settings(worker_online_timeout_seconds=45),
        notification_service=FailingNotificationService(),  # type: ignore[arg-type]
    )
    now = datetime.now(UTC)
    principal = WorkerPrincipal(device_id=device.device_id)
    service.heartbeat(
        principal,
        WorkerHeartbeat(worker_version="0.1.0", started_at=now),
        now=now,
    )

    assert service.reconcile_offline_devices(now=now + timedelta(seconds=46)) == 1
    assert repository.runtime is not None
    assert repository.runtime.connection_status == "offline"
    recovered = service.heartbeat(
        principal,
        WorkerHeartbeat(worker_version="0.1.0", started_at=now),
        now=now + timedelta(seconds=60),
    )
    assert recovered.connection_status == "online"


def test_openapi_exposes_only_whitelisted_worker_task_operations() -> None:
    paths = create_app().openapi()["paths"]
    expected = {
        "/api/v1/tasks",
        "/api/v1/tasks/{task_id}",
        "/api/v1/tasks/active/{device_id}",
        "/api/v1/tasks/{task_id}/events",
        "/api/v1/worker/heartbeat",
        "/api/v1/worker/tasks/claim",
        "/api/v1/worker/tasks/{task_id}/renew",
        "/api/v1/worker/tasks/{task_id}/complete",
        "/api/v1/worker/tasks/{task_id}/fail",
        "/api/v1/worker/tasks/{task_id}/events",
        "/api/v1/worker/provider-inventory",
        "/api/v1/worker/skill-capabilities",
        "/api/v1/devices/{device_id}/provider-inventories",
        "/api/v1/devices/{device_id}/skill-capabilities",
        "/api/v1/automation-app-configs/{provider_code}/{app_id}",
    }
    assert expected <= set(paths)
    assert all("command" not in path for path in paths)


def test_provider_inventory_schema_has_no_device_identity_in_request() -> None:
    data = ProviderInventoryUpsert.model_validate(
        {
            "provider_code": "yingdao",
            "inventory": {
                "provider": "yingdao",
                "available": True,
                "status": "ready",
                "provider_version": "6.3.6",
                "execution_available": True,
                "execution_version": "6.3.6",
                "logged_in": True,
                "account_display": "GY00999",
                "account_type": "PersonalBasic",
                "enterprise_account": False,
                "user_id": "yingdao-user-test",
                "applications": [],
                "discovered_at": "2026-08-20T12:00:00+00:00",
            },
        },
    )

    assert "device_id" not in data.model_dump(mode="json")


def test_worker_replaces_its_own_skill_capability_snapshot() -> None:
    device = Device(device_id=uuid4(), display_name="Worker PC", enabled=True)
    repository = FakeWorkerRepository(device)
    session = FakeSession()
    service = WorkerService(session, repository)  # type: ignore[arg-type]
    principal = WorkerPrincipal(device_id=device.device_id)

    first = service.sync_skill_capabilities(
        principal,
        SkillCapabilitySnapshotUpsert.model_validate(
            {
                "skills": [
                    {
                        "skill_id": "system.echo",
                        "display_name": "Echo",
                        "runtime": "python",
                        "provider": None,
                        "version": "1",
                        "classification": "internal",
                    },
                    {
                        "skill_id": "yingdao.app.run",
                        "display_name": "运行影刀应用",
                        "runtime": "rpa",
                        "provider": "yingdao",
                        "version": "1",
                        "classification": "internal",
                    },
                    {
                        "skill_id": "refund.sync",
                        "display_name": "退款同步",
                        "runtime": "python",
                        "provider": None,
                        "version": "1",
                        "classification": "business",
                    },
                ],
            },
        ),
    )
    assert {item.skill_id for item in first} == {
        "system.echo",
        "yingdao.app.run",
        "refund.sync",
    }
    assert all(item.device_id == device.device_id for item in first)
    assert {item.skill_id: item.classification for item in first} == {
        "refund.sync": "business",
        "system.echo": "internal",
        "yingdao.app.run": "internal",
    }

    second = service.sync_skill_capabilities(
        principal,
        SkillCapabilitySnapshotUpsert.model_validate(
            {
                "skills": [
                    {
                        "skill_id": "system.echo",
                        "display_name": "System Echo",
                        "runtime": "python",
                        "provider": None,
                        "version": "2",
                        "classification": "internal",
                    },
                ],
            },
        ),
    )
    assert [(item.skill_id, item.display_name, item.version) for item in second] == [
        ("system.echo", "System Echo", "2"),
    ]


def test_legacy_snapshot_only_classifies_known_internal_skills() -> None:
    snapshot = SkillCapabilitySnapshotUpsert.model_validate(
        {
            "skills": [
                {
                    "skill_id": "system.echo",
                    "display_name": "Echo",
                    "runtime": "python",
                    "provider": None,
                    "version": "1",
                },
                {
                    "skill_id": "unknown.legacy",
                    "display_name": "Unknown Legacy",
                    "runtime": "python",
                    "provider": None,
                    "version": "1",
                },
            ],
        },
    )

    assert snapshot.skills[0].classification == "internal"
    assert snapshot.skills[1].classification is None


def test_provider_inventory_accepts_unavailable_local_account_classification() -> None:
    data = ProviderInventoryUpsert.model_validate(
        {
            "provider_code": "yingdao",
            "inventory": {
                "provider": "yingdao",
                "available": True,
                "provider_version": "6.3.6",
                "execution_available": True,
                "execution_version": "6.3.6",
                "logged_in": True,
                "account_display": "GY00999",
                "account_type": None,
                "enterprise_account": None,
                "user_id": "yingdao-user-test",
                "applications": [],
                "discovered_at": "2026-08-22T12:00:00+00:00",
            },
        },
    )

    assert data.inventory.account_type is None
    assert data.inventory.enterprise_account is None


def test_provider_inventory_reads_legacy_application_payload_without_500() -> None:
    data = ProviderInventoryUpsert.model_validate(
        {
            "provider_code": "yingdao",
            "inventory": {
                "provider": "yingdao",
                "available": True,
                "provider_version": "6.2.23",
                "logged_in": True,
                "account_display": "legacy",
                "account_type": None,
                "enterprise_account": None,
                "user_id": "legacy-user",
                "applications": [
                    {
                        "app_id": "legacy-app",
                        "app_name": "旧应用",
                        "package_version": "1",
                        "entrypoint": "main",
                    },
                ],
                "discovered_at": "2026-08-22T12:00:00+00:00",
            },
        },
    )

    assert data.inventory.status == "version_unsupported"
    assert data.inventory.available is False
    assert data.inventory.applications[0].version_id == "1"
