from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.devices.exceptions import DeviceNotFoundError
from app.modules.notifications.service import NotificationService
from app.modules.workers.enums import WorkerConnectionStatus
from app.modules.workers.exceptions import (
    WorkerAuthenticationError,
    WorkerCredentialNotFoundError,
    WorkerCredentialStateConflictError,
)
from app.modules.workers.models import (
    DeviceProviderInventory,
    DeviceRuntime,
    DeviceSkillCapability,
    WorkerDeviceCredential,
)
from app.modules.workers.repository import WorkerRepository
from app.modules.workers.schemas import (
    DeviceProviderInventoryRead,
    DeviceRuntimeRead,
    DeviceSkillCapabilityRead,
    ProviderInventoryUpsert,
    SkillCapabilitySnapshotUpsert,
    WorkerCredentialRead,
    WorkerHeartbeat,
    WorkerProvisioningRead,
    WorkerTokenIssuedRead,
    YingdaoProviderInventory,
)
from app.modules.workers.security import (
    generate_worker_token,
    hash_worker_token,
    verify_worker_token,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerPrincipal:
    device_id: UUID


class WorkerService:
    def __init__(
        self,
        session: Session,
        repository: WorkerRepository | None = None,
        settings: Settings | None = None,
        notification_service: NotificationService | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or WorkerRepository(session)
        self.settings = settings or get_settings()
        self.notification_service = notification_service

    def get_credential(self, device_id: UUID) -> WorkerCredentialRead:
        if self.repository.get_device(device_id) is None:
            raise DeviceNotFoundError()
        credential = self.repository.get_credential(device_id)
        if credential is None:
            return WorkerCredentialRead(
                device_id=device_id,
                status="not_issued",
                issued_at=None,
            )
        return WorkerCredentialRead(
            device_id=device_id,
            status="issued" if credential.enabled else "revoked",
            issued_at=credential.created_at,
        )

    def issue_token(self, device_id: UUID) -> str:
        device = self.repository.get_device(device_id)
        if device is None:
            raise DeviceNotFoundError()
        credential = self.repository.get_credential(device_id)
        if credential is not None and credential.enabled:
            raise WorkerCredentialStateConflictError(
                "设备已有有效 Worker 凭证，请使用轮换操作",
            )
        token = generate_worker_token()
        token_hash = hash_worker_token(token)
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

    def rotate_token(self, device_id: UUID) -> str:
        if self.repository.get_device(device_id) is None:
            raise DeviceNotFoundError()
        credential = self.repository.get_credential(device_id)
        if credential is None or not credential.enabled:
            raise WorkerCredentialStateConflictError(
                "设备没有可轮换的有效 Worker 凭证",
            )
        token = generate_worker_token()
        credential.token_hash = hash_worker_token(token)
        self.session.commit()
        return token

    def issue_credential(self, device_id: UUID) -> WorkerTokenIssuedRead:
        token = self.issue_token(device_id)
        credential = self.repository.get_credential(device_id)
        if credential is None:
            raise WorkerCredentialNotFoundError()
        return WorkerTokenIssuedRead(
            device_id=device_id,
            status="issued",
            issued_at=credential.created_at,
            token=token,
        )

    def rotate_credential(self, device_id: UUID) -> WorkerTokenIssuedRead:
        token = self.rotate_token(device_id)
        credential = self.repository.get_credential(device_id)
        if credential is None:
            raise WorkerCredentialNotFoundError()
        return WorkerTokenIssuedRead(
            device_id=device_id,
            status="issued",
            issued_at=credential.created_at,
            token=token,
        )

    def disable_token(self, device_id: UUID) -> None:
        credential = self.repository.get_credential(device_id)
        if credential is None:
            raise WorkerCredentialNotFoundError()
        credential.enabled = False
        self.session.commit()

    def authenticate_token(self, token: str) -> WorkerPrincipal:
        credential = self.repository.get_credential_by_token(token)
        if (
            credential is None
            or not credential.enabled
            or not verify_worker_token(token, credential.token_hash)
            or self.repository.get_device(credential.device_id) is None
        ):
            raise WorkerAuthenticationError()
        return WorkerPrincipal(device_id=credential.device_id)

    def get_provisioning(self, principal: WorkerPrincipal) -> WorkerProvisioningRead:
        device = self.repository.get_device(principal.device_id)
        if device is None:
            raise WorkerAuthenticationError()
        return WorkerProvisioningRead(
            device_id=device.device_id,
            device_display_name=device.display_name,
            device_enabled=device.enabled,
        )

    def authenticate(self, device_id: UUID, token: str) -> WorkerPrincipal:
        device = self.repository.get_device(device_id)
        credential = self.repository.get_credential(device_id)
        if (
            device is None
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
        previous_runtime = self.repository.get_runtime_for_update(principal.device_id)
        previous_status = (
            previous_runtime.connection_status if previous_runtime is not None else None
        )
        previous_offline_since = (
            previous_runtime.offline_since if previous_runtime is not None else None
        )
        runtime = self.repository.upsert_runtime(
            device_id=principal.device_id,
            worker_version=data.worker_version,
            last_seen_at=seen_at,
            started_at=data.started_at,
        )
        self.session.commit()
        device = self.repository.get_device(principal.device_id)
        if (
            previous_status == WorkerConnectionStatus.OFFLINE.value
            and device is not None
            and device.enabled
            and self.notification_service is not None
        ):
            offline_duration = (
                seen_at - previous_offline_since
                if previous_offline_since is not None
                else None
            )
            try:
                self.notification_service.notify_device_recovered(
                    device_name=device.display_name,
                    offline_duration=offline_duration,
                )
            except Exception:
                logger.exception(
                    "Device recovery notification failed device_id=%s",
                    principal.device_id,
                )
        return self.to_runtime_read(runtime, now=seen_at)

    def reconcile_offline_devices(self, *, now: datetime | None = None) -> int:
        observed_at = now or datetime.now(UTC)
        threshold = timedelta(seconds=self.settings.worker_online_timeout_seconds)
        runtimes = self.repository.mark_stale_online_offline(
            stale_before=observed_at - threshold,
            offline_since=observed_at,
        )
        notifications = []
        for runtime in runtimes:
            device = self.repository.get_device(runtime.device_id)
            if device is not None and device.enabled:
                notifications.append((device.display_name, runtime.last_seen_at))
        self.session.commit()
        if self.notification_service is not None:
            for device_name, last_seen_at in notifications:
                try:
                    self.notification_service.notify_device_offline(
                        device_name=device_name,
                        last_heartbeat=last_seen_at,
                    )
                except Exception:
                    logger.exception(
                        "Device offline notification failed device_name=%s",
                        device_name,
                    )
        return len(runtimes)

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

    def save_provider_inventory(
        self,
        principal: WorkerPrincipal,
        data: ProviderInventoryUpsert,
        *,
        now: datetime | None = None,
    ) -> DeviceProviderInventoryRead:
        updated_at = now or datetime.now(UTC)
        inventory = data.inventory
        record = self.repository.upsert_provider_inventory(
            device_id=principal.device_id,
            provider_code=data.provider_code.value,
            available=inventory.available,
            provider_version=inventory.provider_version,
            account_display=inventory.account_display,
            account_type=inventory.account_type,
            enterprise_account=inventory.enterprise_account,
            last_discovered_at=inventory.discovered_at,
            inventory_payload=inventory.model_dump(mode="json"),
            updated_at=updated_at,
        )
        self.session.commit()
        return self.to_provider_inventory_read(record)

    def get_provider_inventory_reads(
        self,
        device_id: UUID,
    ) -> list[DeviceProviderInventoryRead]:
        return [
            self.to_provider_inventory_read(record)
            for record in self.repository.get_provider_inventories(device_id)
        ]

    def sync_skill_capabilities(
        self,
        principal: WorkerPrincipal,
        data: SkillCapabilitySnapshotUpsert,
        *,
        now: datetime | None = None,
    ) -> list[DeviceSkillCapabilityRead]:
        records = self.repository.replace_skill_capabilities(
            device_id=principal.device_id,
            skills=data.skills,
            updated_at=now or datetime.now(UTC),
        )
        self.session.commit()
        return [self.to_skill_capability_read(record) for record in records]

    def get_skill_capability_reads(
        self,
        device_id: UUID,
    ) -> list[DeviceSkillCapabilityRead]:
        return [
            self.to_skill_capability_read(record)
            for record in self.repository.get_skill_capabilities(device_id)
        ]

    def to_runtime_read(
        self,
        runtime: DeviceRuntime,
        *,
        now: datetime,
    ) -> DeviceRuntimeRead:
        del now
        connection_status = WorkerConnectionStatus(runtime.connection_status)
        return DeviceRuntimeRead(
            device_id=runtime.device_id,
            worker_version=runtime.worker_version,
            connection_status=connection_status,
            last_seen_at=runtime.last_seen_at,
            started_at=runtime.started_at,
            updated_at=runtime.updated_at,
        )

    @staticmethod
    def to_provider_inventory_read(
        record: DeviceProviderInventory,
    ) -> DeviceProviderInventoryRead:
        inventory = YingdaoProviderInventory.model_validate(
            record.inventory_payload,
        )
        return DeviceProviderInventoryRead(
            device_id=record.device_id,
            provider_code=record.provider_code,
            available=inventory.available,
            provider_version=inventory.provider_version,
            account_display=inventory.account_display,
            account_type=inventory.account_type,
            enterprise_account=inventory.enterprise_account,
            last_discovered_at=record.last_discovered_at,
            inventory=inventory,
            updated_at=record.updated_at,
        )

    @staticmethod
    def to_skill_capability_read(
        record: DeviceSkillCapability,
    ) -> DeviceSkillCapabilityRead:
        return DeviceSkillCapabilityRead(
            device_id=record.device_id,
            skill_id=record.skill_id,
            display_name=record.display_name,
            runtime=record.runtime,
            provider=record.provider_code,
            version=record.skill_version,
            classification=record.classification,
            updated_at=record.updated_at,
        )
