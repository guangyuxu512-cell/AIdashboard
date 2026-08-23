from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.devices.models import Device
from app.modules.workers.models import (
    DeviceProviderInventory,
    DeviceRuntime,
    DeviceSkillCapability,
    WorkerDeviceCredential,
)
from app.modules.workers.schemas import WorkerSkillDescriptor
from app.modules.workers.security import hash_worker_token


class WorkerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_device(self, device_id: UUID) -> Device | None:
        return self.session.scalar(
            select(Device).where(
                Device.device_id == device_id,
                Device.deleted_at.is_(None),
            ),
        )

    def get_credential(self, device_id: UUID) -> WorkerDeviceCredential | None:
        statement = select(WorkerDeviceCredential).where(
            WorkerDeviceCredential.device_id == device_id,
        )
        return self.session.scalar(statement)

    def get_credential_by_token(
        self,
        token: str,
    ) -> WorkerDeviceCredential | None:
        statement = select(WorkerDeviceCredential).where(
            WorkerDeviceCredential.token_hash == hash_worker_token(token),
        )
        return self.session.scalar(statement)

    def add_credential(self, credential: WorkerDeviceCredential) -> None:
        self.session.add(credential)

    def disable_credentials_by_device(self, device_id: UUID) -> int:
        result = self.session.execute(
            update(WorkerDeviceCredential)
            .where(
                WorkerDeviceCredential.device_id == device_id,
                WorkerDeviceCredential.enabled.is_(True),
            )
            .values(enabled=False),
        )
        return result.rowcount or 0

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
                connection_status="online",
                offline_since=None,
                updated_at=last_seen_at,
            )
            .on_conflict_do_update(
                index_elements=[DeviceRuntime.device_id],
                set_={
                    "worker_version": worker_version,
                    "last_seen_at": last_seen_at,
                    "started_at": started_at,
                    "connection_status": "online",
                    "offline_since": None,
                    "updated_at": last_seen_at,
                },
            )
            .returning(DeviceRuntime)
            .execution_options(populate_existing=True)
        )
        return self.session.execute(statement).scalar_one()

    def get_runtime(self, device_id: UUID) -> DeviceRuntime | None:
        return self.session.get(DeviceRuntime, device_id)

    def get_runtime_for_update(self, device_id: UUID) -> DeviceRuntime | None:
        return self.session.scalar(
            select(DeviceRuntime)
            .where(DeviceRuntime.device_id == device_id)
            .with_for_update(),
        )

    def mark_stale_online_offline(
        self,
        *,
        stale_before: datetime,
        offline_since: datetime,
    ) -> list[DeviceRuntime]:
        runtimes = list(
            self.session.scalars(
                select(DeviceRuntime)
                .join(Device, Device.device_id == DeviceRuntime.device_id)
                .where(
                    DeviceRuntime.connection_status == "online",
                    DeviceRuntime.last_seen_at < stale_before,
                    Device.deleted_at.is_(None),
                )
                .with_for_update(skip_locked=True),
            ),
        )
        for runtime in runtimes:
            runtime.connection_status = "offline"
            runtime.offline_since = offline_since
            runtime.updated_at = offline_since
        return runtimes

    def get_runtimes(self, device_ids: Iterable[UUID]) -> dict[UUID, DeviceRuntime]:
        identifiers = list(device_ids)
        if not identifiers:
            return {}
        statement = select(DeviceRuntime).where(DeviceRuntime.device_id.in_(identifiers))
        return {runtime.device_id: runtime for runtime in self.session.scalars(statement)}

    def upsert_provider_inventory(
        self,
        *,
        device_id: UUID,
        provider_code: str,
        available: bool,
        provider_version: str | None,
        account_display: str | None,
        account_type: str | None,
        enterprise_account: bool | None,
        last_discovered_at: datetime,
        inventory_payload: dict[str, object],
        updated_at: datetime,
    ) -> DeviceProviderInventory:
        statement = (
            insert(DeviceProviderInventory)
            .values(
                device_id=device_id,
                provider_code=provider_code,
                available=available,
                provider_version=provider_version,
                account_display=account_display,
                account_type=account_type,
                enterprise_account=enterprise_account,
                last_discovered_at=last_discovered_at,
                inventory_payload=inventory_payload,
                updated_at=updated_at,
            )
            .on_conflict_do_update(
                index_elements=[
                    DeviceProviderInventory.device_id,
                    DeviceProviderInventory.provider_code,
                ],
                set_={
                    "available": available,
                    "provider_version": provider_version,
                    "account_display": account_display,
                    "account_type": account_type,
                    "enterprise_account": enterprise_account,
                    "last_discovered_at": last_discovered_at,
                    "inventory_payload": inventory_payload,
                    "updated_at": updated_at,
                },
            )
            .returning(DeviceProviderInventory)
            .execution_options(populate_existing=True)
        )
        return self.session.execute(statement).scalar_one()

    def get_provider_inventories(
        self,
        device_id: UUID,
    ) -> list[DeviceProviderInventory]:
        statement = (
            select(DeviceProviderInventory)
            .where(DeviceProviderInventory.device_id == device_id)
            .order_by(DeviceProviderInventory.provider_code.asc())
        )
        return list(self.session.scalars(statement))

    def replace_skill_capabilities(
        self,
        *,
        device_id: UUID,
        skills: list[WorkerSkillDescriptor],
        updated_at: datetime,
    ) -> list[DeviceSkillCapability]:
        skill_ids = [skill.skill_id for skill in skills]
        delete_statement = delete(DeviceSkillCapability).where(
            DeviceSkillCapability.device_id == device_id,
        )
        if skill_ids:
            delete_statement = delete_statement.where(
                DeviceSkillCapability.skill_id.not_in(skill_ids),
            )
        self.session.execute(delete_statement)

        if skills:
            values = [
                {
                    "device_id": device_id,
                    "skill_id": skill.skill_id,
                    "display_name": skill.display_name,
                    "runtime": skill.runtime,
                    "provider_code": skill.provider,
                    "skill_version": skill.version,
                    "classification": (
                        skill.classification.value
                        if skill.classification is not None
                        else None
                    ),
                    "updated_at": updated_at,
                }
                for skill in skills
            ]
            statement = insert(DeviceSkillCapability).values(values)
            statement = statement.on_conflict_do_update(
                index_elements=[
                    DeviceSkillCapability.device_id,
                    DeviceSkillCapability.skill_id,
                ],
                set_={
                    "display_name": statement.excluded.display_name,
                    "runtime": statement.excluded.runtime,
                    "provider_code": statement.excluded.provider_code,
                    "skill_version": statement.excluded.skill_version,
                    "classification": func.coalesce(
                        statement.excluded.classification,
                        DeviceSkillCapability.classification,
                    ),
                    "updated_at": statement.excluded.updated_at,
                },
            )
            self.session.execute(statement)

        return self.get_skill_capabilities(device_id)

    def get_skill_capabilities(
        self,
        device_id: UUID,
    ) -> list[DeviceSkillCapability]:
        statement = (
            select(DeviceSkillCapability)
            .where(DeviceSkillCapability.device_id == device_id)
            .order_by(DeviceSkillCapability.skill_id.asc())
        )
        return list(self.session.scalars(statement))
