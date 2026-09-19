import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.access.contracts import ActorContext
from app.modules.access.service import TeamAuthorizationService
from app.modules.automation_apps.repository import AutomationApplicationConfigRepository
from app.modules.automation_apps.schemas import AutomationInputSchema, normalize_parameters
from app.modules.automation_apps.service import AutomationParameterPresetService
from app.modules.assets.enums import AssetMediaType
from app.modules.assets.models import Asset
from app.modules.assets.repository import AssetRepository
from app.modules.credentials.schemas import TaskAccountPayload
from app.modules.credentials.service import CredentialService
from app.modules.shops.repository import (
    ShopDeviceBindingRepository,
    ShopRepository,
)
from app.modules.tasks.enums import (
    TERMINAL_TASK_STATUS_VALUES,
    TaskSkillId,
    TaskStatus,
)
from app.modules.tasks.exceptions import (
    TaskApplicationNotAvailableError,
    TaskAssetInvalidError,
    TaskDeviceDisabledError,
    TaskEventForbiddenError,
    TaskInputInvalidError,
    TaskNotFoundError,
    TaskProviderLoginRequiredError,
    TaskProviderNotReadyError,
    TaskProviderVersionUnsupportedError,
    TaskSkillNotAvailableError,
    TaskSkillSchemaUnavailableError,
    TaskShopDeviceBindingInvalidError,
    TaskShopInvalidError,
    TaskStateConflictError,
    TaskTargetDeviceInvalidError,
    TaskWorkerOfflineError,
)
from app.modules.tasks.models import Task, TaskAsset, TaskShop
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schemas import (
    ActiveTaskSummaryRead,
    TaskComplete,
    TaskCreate,
    TaskEventBatchResult,
    TaskEventBatchWrite,
    TaskEventListRead,
    TaskEventPurgeRead,
    TaskFail,
    TaskListItemRead,
    TaskProgressSummaryRead,
    task_event_to_read,
)
from app.modules.tasks.skill_contracts import validate_skill_input
from app.modules.workers.models import DeviceSkillCapability
from app.modules.workers.business_skill_schema import (
    BusinessSkillInputValidationError,
    BusinessSkillSchemaUnavailableError,
    BusinessSkillSchemaUnsupportedError,
)
from app.modules.workers.schemas import YingdaoProviderInventory
from app.modules.workers.service import WorkerPrincipal
from app.shared.pagination import Page


@dataclass(frozen=True)
class PreparedTaskCreation:
    input_json: dict[str, Any]
    execution_display_name: str
    parameter_preset_id: UUID | None = None
    parameter_preset_version: int | None = None


@dataclass(frozen=True)
class ClaimedWorkerTask:
    task: Task
    accounts: list[TaskAccountPayload]
    assets: list[Asset]


_SHOP_NAME_MINIMUM_WORKER_VERSION = (0, 4, 7)


def _supports_task_account_shop_name(worker_version: str | None) -> bool:
    """Only send the additive account field to Workers that can parse it."""
    if not worker_version:
        return False
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:[-+].*)?", worker_version)
    if match is None:
        return False
    return tuple(int(part) for part in match.groups()) >= _SHOP_NAME_MINIMUM_WORKER_VERSION


class TaskService:
    def __init__(
        self,
        session: Session,
        repository: TaskRepository | None = None,
        settings: Settings | None = None,
        application_config_repository: (
            AutomationApplicationConfigRepository | None
        ) = None,
        parameter_preset_service: AutomationParameterPresetService | None = None,
        credential_service: CredentialService | None = None,
        shop_repository: ShopRepository | None = None,
        shop_device_binding_repository: ShopDeviceBindingRepository | None = None,
        asset_repository: AssetRepository | None = None,
        team_authorization_service: TeamAuthorizationService | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or TaskRepository(session)
        self.settings = settings or get_settings()
        self.application_config_repository = (
            application_config_repository
            or AutomationApplicationConfigRepository(session)
        )
        self.parameter_preset_service = parameter_preset_service or AutomationParameterPresetService(
            session,
            config_repository=self.application_config_repository,
        )
        self.credential_service = credential_service
        self.shop_repository = shop_repository or ShopRepository(session)
        self.shop_device_binding_repository = (
            shop_device_binding_repository or ShopDeviceBindingRepository(session)
        )
        self.asset_repository = asset_repository or AssetRepository(session)
        self.team_authorization_service = (
            team_authorization_service or TeamAuthorizationService(session)
        )

    def create(self, data: TaskCreate, actor: ActorContext) -> Task:
        task = self._create_pending(
            data,
            require_worker_online=True,
            team_id=actor.require_team_id(),
            created_by_user_id=actor.user_id,
            actor=actor,
        )
        self.session.commit()
        self.session.refresh(task)
        return task

    def prepare_scheduled_task(
        self,
        data: TaskCreate,
        *,
        team_id: UUID,
        actor: ActorContext | None = None,
    ) -> PreparedTaskCreation:
        """Validate a future Task while allowing its Worker to be offline.

        Schedules still require an enabled Device, declared Skill, ready Provider,
        available Application and valid input. Worker connectivity is deliberately
        deferred until the ordinary pending Task is claimed.
        """

        return self._prepare_creation(
            data,
            require_worker_online=False,
            team_id=team_id,
            actor=actor,
        )

    def create_for_schedule(
        self,
        data: TaskCreate,
        *,
        team_id: UUID,
        created_by_user_id: UUID | None,
        actor: ActorContext | None = None,
    ) -> Task:
        """Add a validated pending Task without committing the outer transaction."""

        return self._create_pending(
            data,
            require_worker_online=False,
            team_id=team_id,
            created_by_user_id=created_by_user_id,
            actor=actor,
        )

    def _create_pending(
        self,
        data: TaskCreate,
        *,
        require_worker_online: bool,
        team_id: UUID,
        created_by_user_id: UUID | None,
        actor: ActorContext | None,
    ) -> Task:
        prepared = self._prepare_creation(
            data,
            require_worker_online=require_worker_online,
            team_id=team_id,
            actor=actor,
        )
        task = Task(
            team_id=team_id,
            created_by_user_id=created_by_user_id,
            target_device_id=data.target_device_id,
            parameter_preset_id=prepared.parameter_preset_id,
            parameter_preset_version=prepared.parameter_preset_version,
            skill_id=data.skill_id,
            execution_display_name=prepared.execution_display_name,
            status=TaskStatus.PENDING.value,
            input_json=prepared.input_json,
            shop_links=[
                TaskShop(shop_id=shop_id, position=position)
                for position, shop_id in enumerate(data.shop_ids)
            ],
            asset_links=[
                TaskAsset(asset_id=asset_id, position=position)
                for position, asset_id in enumerate(data.asset_ids)
            ],
        )
        self.repository.add(task)
        return task

    def _prepare_creation(
        self,
        data: TaskCreate,
        *,
        require_worker_online: bool,
        team_id: UUID,
        actor: ActorContext | None,
    ) -> PreparedTaskCreation:
        if (
            data.parameter_preset_id is not None
            and data.skill_id != TaskSkillId.YINGDAO_APP_RUN
        ):
            raise TaskInputInvalidError("影刀参数预设只支持 yingdao.app.run")
        self.team_authorization_service.require_execution_resources(
            team_id=team_id,
            device_id=data.target_device_id,
            shop_ids=data.shop_ids,
        )
        device = self.repository.get_task_target_device(data.target_device_id)
        if device is None:
            raise TaskTargetDeviceInvalidError()
        if not device.enabled:
            raise TaskDeviceDisabledError()
        self._validate_shop_context(data.target_device_id, data.shop_ids)
        self._validate_asset_context(data.asset_ids, team_id=team_id)
        if require_worker_online:
            runtime = self.repository.get_device_runtime(data.target_device_id)
            if runtime is None or runtime.connection_status != "online":
                raise TaskWorkerOfflineError()
        capability = self.repository.get_skill_capability(
            data.target_device_id,
            data.skill_id,
        )
        if capability is None:
            raise TaskSkillNotAvailableError(
                details={"skill_id": data.skill_id},
            )
        provider_inventory = self._validate_provider_dependency(
            data.target_device_id,
            capability,
        )
        try:
            input_json = validate_skill_input(
                data.skill_id,
                data.input,
                classification=capability.classification,
                input_schema=capability.input_schema,
            )
        except ValidationError as error:
            raise TaskInputInvalidError(
                details=error.errors(include_input=False),
            ) from error
        except BusinessSkillInputValidationError as error:
            raise TaskInputInvalidError(str(error)) from error
        except (
            BusinessSkillSchemaUnavailableError,
            BusinessSkillSchemaUnsupportedError,
        ) as error:
            raise TaskSkillSchemaUnavailableError(
                details={"skill_id": data.skill_id, "reason": str(error)},
            ) from error
        execution_display_name = capability.display_name
        if data.skill_id == TaskSkillId.YINGDAO_APP_RUN:
            (
                input_json,
                execution_display_name,
                parameter_preset_version,
            ) = self._validate_yingdao_application_run(
                input_json,
                provider_inventory,
                parameter_preset_id=data.parameter_preset_id,
                team_id=team_id,
                actor=actor,
                shop_ids=data.shop_ids,
            )
        return PreparedTaskCreation(
            input_json=input_json,
            execution_display_name=execution_display_name,
            parameter_preset_id=data.parameter_preset_id,
            parameter_preset_version=(
                parameter_preset_version
                if data.parameter_preset_id is not None
                else None
            ),
        )

    def _validate_asset_context(
        self,
        asset_ids: list[UUID],
        *,
        team_id: UUID,
    ) -> None:
        if not asset_ids:
            return
        assets_by_id = {
            asset.asset_id: asset
            for asset in self.asset_repository.list_by_ids(asset_ids)
        }
        invalid_ids = [
            asset_id
            for asset_id in asset_ids
            if asset_id not in assets_by_id
            or assets_by_id[asset_id].media_type != AssetMediaType.IMAGE.value
            or assets_by_id[asset_id].team_id != team_id
        ]
        if invalid_ids:
            raise TaskAssetInvalidError(
                details={"asset_ids": [str(asset_id) for asset_id in invalid_ids]},
            )

    def _validate_shop_context(
        self,
        device_id: UUID,
        shop_ids: list[UUID],
    ) -> None:
        if not shop_ids:
            return
        shops_by_id = {
            shop.shop_id: shop for shop in self.shop_repository.list_by_ids(shop_ids)
        }
        invalid_shop_ids = [
            shop_id
            for shop_id in shop_ids
            if shop_id not in shops_by_id or not shops_by_id[shop_id].enabled
        ]
        if invalid_shop_ids:
            raise TaskShopInvalidError(
                details={"shop_ids": [str(shop_id) for shop_id in invalid_shop_ids]},
            )
        enabled_binding_shop_ids = (
            self.shop_device_binding_repository.list_enabled_shop_ids_for_device(
                device_id,
                shop_ids,
            )
        )
        unbound_shop_ids = [
            shop_id for shop_id in shop_ids if shop_id not in enabled_binding_shop_ids
        ]
        if unbound_shop_ids:
            raise TaskShopDeviceBindingInvalidError(
                details={"shop_ids": [str(shop_id) for shop_id in unbound_shop_ids]},
            )
        self._require_credential_service().ensure_task_accounts_available(shop_ids)

    def _validate_provider_dependency(
        self,
        device_id: UUID,
        capability: DeviceSkillCapability,
    ) -> YingdaoProviderInventory | None:
        if capability.provider_code is None or capability.runtime == "discovery":
            return None
        if capability.provider_code != "yingdao":
            raise TaskProviderNotReadyError(
                details={"provider": capability.provider_code},
            )
        record = self.repository.get_provider_inventory(
            device_id,
            capability.provider_code,
        )
        if record is None:
            raise TaskProviderNotReadyError(details={"provider": "yingdao"})
        try:
            inventory = YingdaoProviderInventory.model_validate(
                record.inventory_payload,
            )
        except ValidationError as error:
            raise TaskProviderNotReadyError(
                details={"provider": "yingdao", "reason": "invalid_inventory"},
            ) from error
        if inventory.status == "need_login" or not inventory.logged_in:
            raise TaskProviderLoginRequiredError()
        if (
            inventory.status == "version_unsupported"
            or inventory.provider_version != "6.3.6"
            or inventory.execution_version != "6.3.6"
        ):
            raise TaskProviderVersionUnsupportedError(
                details={"required_version": "6.3.6"},
            )
        if (
            inventory.status != "ready"
            or not record.available
            or not inventory.available
            or not inventory.execution_available
        ):
            raise TaskProviderNotReadyError(details={"provider": "yingdao"})
        return inventory

    def _validate_yingdao_application_run(
        self,
        input_json: dict[str, Any],
        inventory: YingdaoProviderInventory | None,
        *,
        parameter_preset_id: UUID | None,
        team_id: UUID,
        actor: ActorContext | None,
        shop_ids: list[UUID],
    ) -> tuple[dict[str, Any], str, int | None]:
        if inventory is None:
            raise TaskProviderNotReadyError(details={"provider": "yingdao"})
        app_id = str(input_json["app_id"])
        application = next(
            (
                application
                for application in inventory.applications
                if application.app_id == app_id
            ),
            None,
        )
        if application is None:
            raise TaskApplicationNotAvailableError(
                details={"app_id": app_id},
            )
        if parameter_preset_id is not None:
            snapshot = (
                self.parameter_preset_service.snapshot_for_actor(
                    actor=actor,
                    app_id=app_id,
                    preset_id=parameter_preset_id,
                    shop_ids=shop_ids,
                )
                if actor is not None
                else self.parameter_preset_service.snapshot_for_team(
                    team_id=team_id,
                    app_id=app_id,
                    preset_id=parameter_preset_id,
                    shop_ids=shop_ids,
                )
            )
            params = snapshot.parameters
            preset_version = snapshot.preset_version
        else:
            config = self.application_config_repository.get("yingdao", app_id)
            schema = AutomationInputSchema.model_validate(
                config.input_schema if config is not None else {"fields": []},
            )
            try:
                params = normalize_parameters(schema, input_json.get("params", {}))
            except ValueError as error:
                raise TaskInputInvalidError(str(error)) from error
            preset_version = None
        return {"app_id": app_id, "params": params}, application.app_name, preset_version

    def get(self, actor: ActorContext, task_id: UUID) -> Task:
        task = self.repository.get_for_actor(actor=actor, task_id=task_id)
        if task is None:
            raise TaskNotFoundError()
        return task

    def get_active_summary(
        self,
        actor: ActorContext,
        device_id: UUID,
    ) -> ActiveTaskSummaryRead | None:
        task = self.repository.get_active_for_device(
            actor=actor,
            device_id=device_id,
        )
        if task is None:
            return None
        latest_event = self.repository.get_latest_event(task.task_id)
        return ActiveTaskSummaryRead(
            task_id=task.task_id,
            target_device_id=task.target_device_id,
            skill_id=task.skill_id,
            execution_display_name=task.execution_display_name,
            status=task.status,
            started_at=task.started_at,
            created_at=task.created_at,
            latest_event=(
                task_event_to_read(latest_event) if latest_event is not None else None
            ),
        )

    def list_management_tasks(
        self,
        *,
        actor: ActorContext,
        page: int,
        page_size: int,
        status: TaskStatus | None,
        device_id: UUID | None,
        search: str | None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> Page[TaskListItemRead]:
        normalized_search = search.strip() if search else None
        records, total = self.repository.list_management_tasks(
            actor=actor,
            offset=(page - 1) * page_size,
            limit=page_size,
            status=status,
            device_id=device_id,
            search=normalized_search or None,
            created_from=created_from,
            created_to=created_to,
        )
        items = []
        for record in records:
            task = record.task
            progress = _progress_summary(record.progress_metadata)
            current_message = _task_current_message(
                status=TaskStatus(task.status),
                error_message=task.error_message,
                progress_message=record.progress_message,
                status_message=record.status_message,
                log_message=record.log_message,
            )
            items.append(
                TaskListItemRead(
                    task_id=task.task_id,
                    target_device_id=task.target_device_id,
                    device_display_name=record.device_display_name,
                    skill_id=task.skill_id,
                    skill_display_name=record.skill_display_name,
                    execution_display_name=task.execution_display_name,
                    status=task.status,
                    progress=progress,
                    current_message=current_message,
                    started_at=task.started_at,
                    finished_at=task.finished_at,
                    created_at=task.created_at,
                ),
            )
        return Page(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    def list_events(
        self,
        actor: ActorContext,
        task_id: UUID,
        *,
        after_seq: int | None,
        before_seq: int | None = None,
        limit: int,
    ) -> TaskEventListRead:
        if self.repository.get_for_actor(actor=actor, task_id=task_id) is None:
            raise TaskNotFoundError()
        if after_seq is not None and before_seq is not None:
            raise ValueError("after_seq and before_seq cannot be used together")
        page = self.repository.list_events(
            task_id=task_id,
            after_seq=after_seq,
            before_seq=before_seq,
            limit=limit,
        )
        items = [task_event_to_read(event) for event in page.items]
        return TaskEventListRead(
            task_id=task_id,
            after_seq=after_seq,
            before_seq=before_seq,
            next_after_seq=(
                items[-1].seq
                if items
                else (after_seq if after_seq is not None else 0)
            ),
            next_before_seq=(
                items[0].seq if items and page.has_more_before else None
            ),
            has_more_before=page.has_more_before,
            items=items,
        )

    def purge_expired_events(
        self,
        *,
        now: datetime | None = None,
    ) -> TaskEventPurgeRead:
        purged_at = now or datetime.now(UTC)
        cutoff = purged_at - timedelta(days=self.settings.task_event_retention_days)
        tasks_purged = 0
        events_deleted = 0
        while True:
            batch = self.repository.purge_expired_event_batch(
                cutoff=cutoff,
                purged_at=purged_at,
                batch_size=self.settings.task_event_retention_batch_size,
            )
            if batch.events_deleted == 0:
                self.session.rollback()
                break
            self.session.commit()
            tasks_purged += batch.tasks_purged
            events_deleted += batch.events_deleted
        return TaskEventPurgeRead(
            cutoff=cutoff,
            tasks_purged=tasks_purged,
            events_deleted=events_deleted,
        )

    def purge_expired_events_for_actor(
        self,
        actor: ActorContext,
        *,
        now: datetime | None = None,
    ) -> TaskEventPurgeRead:
        purged_at = now or datetime.now(UTC)
        cutoff = purged_at - timedelta(days=self.settings.task_event_retention_days)
        tasks_purged = 0
        events_deleted = 0
        while True:
            batch = self.repository.purge_expired_event_batch(
                cutoff=cutoff,
                purged_at=purged_at,
                batch_size=self.settings.task_event_retention_batch_size,
                actor=actor,
            )
            if batch.events_deleted == 0:
                self.session.rollback()
                break
            self.session.commit()
            tasks_purged += batch.tasks_purged
            events_deleted += batch.events_deleted
        return TaskEventPurgeRead(
            cutoff=cutoff,
            tasks_purged=tasks_purged,
            events_deleted=events_deleted,
        )

    def append_events(
        self,
        principal: WorkerPrincipal,
        task_id: UUID,
        data: TaskEventBatchWrite,
        *,
        now: datetime | None = None,
    ) -> TaskEventBatchResult:
        task = self.repository.get(task_id)
        if task is None:
            raise TaskNotFoundError()
        current_time = now or datetime.now(UTC)
        owns_running_lease = (
            task.status == TaskStatus.RUNNING.value
            and task.lease_until is not None
            and task.lease_until >= current_time
        )
        owns_terminal_task = task.status in TERMINAL_TASK_STATUS_VALUES
        if (
            task.target_device_id != principal.device_id
            or not (owns_running_lease or owns_terminal_task)
        ):
            raise TaskEventForbiddenError()

        payloads = [
            {
                "seq": event.seq,
                "event_type": event.event_type.value,
                "level": event.level,
                "message": _redact_message(event.message),
                "event_at": event.event_at,
                "metadata_json": _redact_metadata(event.metadata),
            }
            for event in data.events
        ]
        accepted_count = self.repository.insert_events(
            task_id=task_id,
            events=payloads,
        )
        self.session.commit()
        return TaskEventBatchResult(
            task_id=task_id,
            accepted_count=accepted_count,
            highest_seq=max(event.seq for event in data.events),
        )

    def claim(
        self,
        principal: WorkerPrincipal,
        *,
        now: datetime | None = None,
    ) -> Task | None:
        task = self._claim_without_commit(principal, now=now)
        self.session.commit()
        return task

    def claim_with_account(
        self,
        principal: WorkerPrincipal,
        *,
        now: datetime | None = None,
    ) -> ClaimedWorkerTask | None:
        task = self._claim_without_commit(principal, now=now)
        if task is None:
            self.session.commit()
            return None
        try:
            runtime = self.repository.get_device_runtime(principal.device_id)
            accounts = (
                self._require_credential_service().build_task_account_payloads(
                    task.shop_ids,
                    include_shop_name=_supports_task_account_shop_name(
                        getattr(runtime, "worker_version", None),
                    ),
                )
                if task.shop_ids
                else []
            )
            assets_by_id = {
                asset.asset_id: asset
                for asset in self.asset_repository.list_by_ids(task.asset_ids)
            }
            assets = [assets_by_id[asset_id] for asset_id in task.asset_ids]
        except Exception:
            self.session.rollback()
            raise
        self.session.commit()
        return ClaimedWorkerTask(task=task, accounts=accounts, assets=assets)

    def _claim_without_commit(
        self,
        principal: WorkerPrincipal,
        *,
        now: datetime | None,
    ) -> Task | None:
        claimed_at = now or datetime.now(UTC)
        if self.repository.get_enabled_device(principal.device_id) is None:
            self.session.rollback()
            return None
        lease_until = claimed_at + timedelta(
            seconds=self.settings.worker_task_lease_seconds,
        )
        return self.repository.claim_next(
            device_id=principal.device_id,
            now=claimed_at,
            lease_until=lease_until,
        )

    def _require_credential_service(self) -> CredentialService:
        if self.credential_service is None:
            raise RuntimeError(
                "CredentialService is required for a shop-scoped Task",
            )
        return self.credential_service

    def renew(
        self,
        principal: WorkerPrincipal,
        task_id: UUID,
        *,
        now: datetime | None = None,
    ) -> Task:
        renewed_at = now or datetime.now(UTC)
        task = self.repository.renew(
            task_id=task_id,
            device_id=principal.device_id,
            now=renewed_at,
            lease_until=renewed_at
            + timedelta(seconds=self.settings.worker_task_lease_seconds),
        )
        if task is None:
            self.session.rollback()
            raise TaskStateConflictError()
        self.session.commit()
        return task

    def complete(
        self,
        principal: WorkerPrincipal,
        task_id: UUID,
        data: TaskComplete,
        *,
        now: datetime | None = None,
    ) -> Task:
        return self._finish(
            principal,
            task_id,
            status=TaskStatus.SUCCESS,
            result=_redact_metadata(data.result),
            error_code=None,
            error_message=None,
            now=now,
        )

    def fail(
        self,
        principal: WorkerPrincipal,
        task_id: UUID,
        data: TaskFail,
        *,
        now: datetime | None = None,
    ) -> Task:
        return self._finish(
            principal,
            task_id,
            status=TaskStatus.FAILED,
            result=None,
            error_code=data.error_code,
            error_message=_redact_message(data.error_message),
            now=now,
        )

    def _finish(
        self,
        principal: WorkerPrincipal,
        task_id: UUID,
        *,
        status: TaskStatus,
        result: dict[str, object] | None,
        error_code: str | None,
        error_message: str | None,
        now: datetime | None,
    ) -> Task:
        finished_at = now or datetime.now(UTC)
        task = self.repository.complete(
            task_id=task_id,
            device_id=principal.device_id,
            now=finished_at,
            result=result,
            error_code=error_code,
            error_message=error_message,
            status=status,
        )
        if task is None:
            self.session.rollback()
            raise TaskStateConflictError()
        self.session.commit()
        return task

    def reconcile_expired(self, *, now: datetime | None = None) -> int:
        count = self.repository.mark_expired_lost(now=now or datetime.now(UTC))
        self.session.commit()
        return count


_SENSITIVE_MESSAGE = re.compile(
    r"(?i)(?P<prefix>[\"']?"
    r"(?:account|login_identifier|preferred_verification_channel|password|token|"
    r"authorization|cookie|secret|登录账号|登录密码|首选验证方式)[\"']?\s*[:=]\s*)"
    r"(?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^\s,;}]+)",
)
_ACCOUNT_PAYLOAD_REQUIRED_KEYS = frozenset({"login_identifier", "secret"})
_CHINESE_ACCOUNT_PAYLOAD_REQUIRED_KEYS = frozenset({"登录账号", "登录密码"})
_ACCOUNT_CONTAINER_KEYS = frozenset({"accounts", "店铺列表"})
_SENSITIVE_KEYS = frozenset(
    {
        "account",
        "authorization",
        "cookie",
        "cookies",
        "login_identifier",
        "password",
        "preferred_verification_channel",
        "secret",
        "token",
        "登录账号",
        "登录密码",
        "首选验证方式",
    },
)


def _redact_message(value: str) -> str:
    without_account_payload = _redact_embedded_account_payload(value)
    return _SENSITIVE_MESSAGE.sub(
        lambda match: f"{match.group('prefix')}[REDACTED]",
        without_account_payload,
    )


def _is_account_payload(value: object) -> bool:
    if isinstance(value, dict):
        normalized_keys = {str(key).lower() for key in value}
        if _ACCOUNT_PAYLOAD_REQUIRED_KEYS.issubset(normalized_keys):
            return True
        if _CHINESE_ACCOUNT_PAYLOAD_REQUIRED_KEYS.issubset(value.keys()):
            return True
        for list_key in ("accounts", "店铺列表"):
            accounts = value.get(list_key)
            if isinstance(accounts, list) and any(
                _is_account_payload(account) for account in accounts
            ):
                return True
        return False
    return isinstance(value, list) and any(
        _is_account_payload(account) for account in value
    )


def _redact_embedded_account_payload(value: str) -> str:
    """Remove observed English or Chinese account payloads from task logs."""

    decoder = json.JSONDecoder()
    cursor = 0
    fragments: list[str] = []
    while True:
        object_starts = [
            position
            for position in (value.find("{", cursor), value.find("[", cursor))
            if position >= 0
        ]
        if not object_starts:
            fragments.append(value[cursor:])
            return "".join(fragments)
        object_start = min(object_starts)
        try:
            payload, consumed = decoder.raw_decode(value[object_start:])
        except json.JSONDecodeError:
            fragments.append(value[cursor : object_start + 1])
            cursor = object_start + 1
            continue
        if _is_account_payload(payload):
            fragments.append(value[cursor:object_start])
            fragments.append("[ACCOUNT_PAYLOAD_REDACTED]")
            cursor = object_start + consumed
            continue
        fragments.append(value[cursor : object_start + 1])
        cursor = object_start + 1


def _redact_metadata(value: dict[str, Any]) -> dict[str, Any]:
    def redact(item: Any, key: str | None = None) -> Any:
        if key is not None and key.lower() in _ACCOUNT_CONTAINER_KEYS:
            return "[ACCOUNT_PAYLOAD_REDACTED]"
        if key is not None and key.lower() in _SENSITIVE_KEYS:
            return "[REDACTED]"
        if isinstance(item, dict):
            return {
                str(child_key): redact(child, str(child_key))
                for child_key, child in item.items()
            }
        if isinstance(item, list):
            return [redact(child) for child in item]
        return item

    return redact(value)


def _progress_summary(
    metadata: dict[str, Any] | None,
) -> TaskProgressSummaryRead | None:
    if not isinstance(metadata, dict):
        return None
    current = metadata.get("current")
    total = metadata.get("total")
    if isinstance(current, bool) or not isinstance(current, int) or current < 0:
        return None
    if total is not None:
        if isinstance(total, bool) or not isinstance(total, int) or total <= 0:
            return None
        if current > total:
            return None
    return TaskProgressSummaryRead(current=current, total=total)


def _task_current_message(
    *,
    status: TaskStatus,
    error_message: str | None,
    progress_message: str | None,
    status_message: str | None,
    log_message: str | None,
) -> str | None:
    if status in {TaskStatus.FAILED, TaskStatus.LOST} and error_message:
        return _safe_summary(error_message)
    for message in (progress_message, status_message, log_message):
        summary = _safe_summary(message)
        if summary:
            return summary
    if status is TaskStatus.SUCCESS:
        return "完成"
    return None


def _safe_summary(value: str | None, *, max_length: int = 500) -> str | None:
    if not value:
        return None
    summary = _redact_message(value).strip()
    if not summary:
        return None
    if len(summary) <= max_length:
        return summary
    return f"{summary[: max_length - 1]}…"
