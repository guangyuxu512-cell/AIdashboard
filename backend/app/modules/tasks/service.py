import json
import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.access.contracts import ActorContext
from app.modules.access.service import TeamAuthorizationService
from app.modules.assets.enums import AssetMediaType
from app.modules.assets.models import Asset
from app.modules.assets.repository import AssetRepository
from app.modules.tasks.enums import (
    TERMINAL_TASK_STATUS_VALUES,
    TaskStatus,
)
from app.modules.tasks.exceptions import (
    TaskAssetInvalidError,
    TaskDeviceDisabledError,
    TaskEventForbiddenError,
    TaskInputInvalidError,
    TaskNotFoundError,
    TaskSkillNotAvailableError,
    TaskSkillSchemaUnavailableError,
    TaskStateConflictError,
    TaskTargetDeviceInvalidError,
    TaskWorkerOfflineError,
)
from app.modules.tasks.models import Task, TaskAsset
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
from app.modules.workers.business_skill_schema import (
    BusinessSkillInputValidationError,
    BusinessSkillSchemaUnavailableError,
    BusinessSkillSchemaUnsupportedError,
)
from app.modules.workers.service import WorkerPrincipal
from app.modules.workers.shop_context import LOCAL_SHOPS_KEY, resolve_worker_shops, worker_shop_snapshot_matches
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
    assets: list[Asset]
    local_shops: list[dict[str, Any]]


def _supports_local_shop_context(worker_version: str | None) -> bool:
    """Older Workers reject additive task fields; do not assign them mapped tasks."""
    if not isinstance(worker_version, str) or not worker_version:
        return False
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:[-+].*)?", worker_version)
    if match is None:
        return False
    return tuple(int(part) for part in match.groups()) >= (0, 5, 7)


def _supports_operations_delivery(worker_version: str | None) -> bool:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:[-+].*)?", worker_version or "")
    return bool(match and tuple(int(part) for part in match.groups()) >= (0, 5, 9))


class TaskService:
    def __init__(
        self,
        session: Session,
        repository: TaskRepository | None = None,
        settings: Settings | None = None,
        asset_repository: AssetRepository | None = None,
        team_authorization_service: TeamAuthorizationService | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or TaskRepository(session)
        self.settings = settings or get_settings()
        self.asset_repository = asset_repository or AssetRepository(session)
        self.team_authorization_service = (
            team_authorization_service or TeamAuthorizationService(session)
        )

    def create(self, data: TaskCreate, actor: ActorContext) -> Task:
        team_id = actor.require_team_id()
        request_hash = None
        if data.skill_id == 'douyin.compass_selection':
            try:
                correlation = str(UUID(data.input['correlation_id']))
                if correlation != data.input['correlation_id']:
                    raise ValueError('noncanonical correlation')
            except (KeyError, TypeError, ValueError, AttributeError):
                raise TaskInputInvalidError('选品任务关联标识无效') from None
            try:
                request_hash = hashlib.sha256(json.dumps(data.model_dump(mode='json'), ensure_ascii=False,
                    sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
            except (ValueError, TypeError):
                raise TaskInputInvalidError('选品任务参数无效') from None
            self.session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(
                'operations-selection:' + correlation, 0))))
            existing = self.session.scalar(select(Task).where(
                Task.skill_id == data.skill_id, Task.input_json['correlation_id'].astext == correlation))
            if existing is not None:
                if (existing.team_id != team_id or existing.created_by_user_id != actor.user_id
                        or existing.input_json.get('_operations_request_hash') != request_hash):
                    raise TaskStateConflictError()
                self.team_authorization_service.require_execution_resources(
                    team_id=team_id, device_id=data.target_device_id)
                self.session.commit()
                return existing
        task = self._create_pending(
            data,
            require_worker_online=True,
            team_id=team_id,
            created_by_user_id=actor.user_id,
            actor=actor,
        )
        if request_hash is not None:
            task.input_json = {**task.input_json, '_operations_request_hash': request_hash}
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

        Schedules still require an enabled Device, declared Skill and valid input.
        Worker connectivity is deliberately
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
        if data.skill_id.startswith("yingdao.") or data.parameter_preset_id is not None:
            raise TaskInputInvalidError("影刀任务已停用，请使用 Worker 技能包")
        if LOCAL_SHOPS_KEY in data.input:
            raise TaskInputInvalidError("本机店铺只能从设备清单选择")
        self.team_authorization_service.require_execution_resources(
            team_id=team_id,
            device_id=data.target_device_id,
        )
        device = self.repository.get_task_target_device(data.target_device_id)
        if device is None:
            raise TaskTargetDeviceInvalidError()
        if not device.enabled:
            raise TaskDeviceDisabledError()
        local_shops = resolve_worker_shops(
            self.session, data.target_device_id, data.local_shop_ids, require_available=require_worker_online,
        )
        self._validate_asset_context(data.asset_ids, team_id=team_id)
        if require_worker_online:
            runtime = self.repository.get_device_runtime(data.target_device_id)
            if runtime is None or runtime.connection_status != "online":
                raise TaskWorkerOfflineError()
        if data.skill_id == "douyin.compass_selection":
            runtime = self.repository.get_device_runtime(data.target_device_id)
            if runtime is None or not _supports_operations_delivery(runtime.worker_version):
                raise TaskInputInvalidError("该设备的 Worker 尚不支持选品结果回传")
            if (len(local_shops) != 1 or local_shops[0].get("platform") != "douyin"
                    or not local_shops[0].get("platform_shop_id")):
                raise TaskInputInvalidError("选品需要选择一家具备平台身份的本机店铺")
            if not self.settings.operations_selection_origin:
                raise TaskInputInvalidError("运营中心结果接收服务未配置")
        capability = self.repository.get_skill_capability(
            data.target_device_id,
            data.skill_id,
        )
        if capability is None:
            raise TaskSkillNotAvailableError(
                details={"skill_id": data.skill_id},
            )
        if capability.provider_code is not None or capability.runtime != "python":
            raise TaskInputInvalidError("仅支持 Worker 本机技能")
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
        if local_shops:
            input_json[LOCAL_SHOPS_KEY] = local_shops
        return PreparedTaskCreation(
            input_json=input_json,
            execution_display_name=capability.display_name,
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

    def claim_with_context(
        self,
        principal: WorkerPrincipal,
        *,
        now: datetime | None = None,
        precheck_only: bool = False,
    ) -> ClaimedWorkerTask | None:
        task = self._claim_without_commit(principal, now=now, precheck_only=precheck_only)
        if task is None:
            self.session.commit()
            return None
        local_shops = task.input_json.get(LOCAL_SHOPS_KEY, [])
        if not worker_shop_snapshot_matches(self.session, principal.device_id, local_shops):
            task.status = TaskStatus.FAILED.value
            task.error_code = "WORKER_SHOP_MAPPING_CHANGED"
            task.error_message = "设备店铺映射已变化，请重新选择店铺"
            task.lease_until = None
            task.finished_at = now or datetime.now(UTC)
            self.session.commit()
            return None
        try:
            assets_by_id = {
                asset.asset_id: asset
                for asset in self.asset_repository.list_by_ids(task.asset_ids)
            }
            assets = [assets_by_id[asset_id] for asset_id in task.asset_ids]
        except Exception:
            self.session.rollback()
            raise
        self.session.commit()
        return ClaimedWorkerTask(task=task, assets=assets, local_shops=local_shops)

    def _claim_without_commit(
        self,
        principal: WorkerPrincipal,
        *,
        now: datetime | None,
        precheck_only: bool = False,
    ) -> Task | None:
        claimed_at = now or datetime.now(UTC)
        if self.repository.get_enabled_device(principal.device_id) is None:
            self.session.rollback()
            return None
        lease_until = claimed_at + timedelta(
            seconds=self.settings.worker_task_lease_seconds,
        )
        runtime = self.repository.get_device_runtime(principal.device_id)
        return self.repository.claim_next(
            device_id=principal.device_id,
            now=claimed_at,
            lease_until=lease_until,
            precheck_only=precheck_only,
            local_context_supported=_supports_local_shop_context(getattr(runtime, "worker_version", None)),
            operations_delivery_supported=_supports_operations_delivery(getattr(runtime, "worker_version", None)),
        )

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
            # The server may have committed the terminal while its response
            # was lost.  Accept an identical replay from the same device;
            # different results and expired/LOST tasks remain conflicts.
            existing = self.repository.get(task_id)
            if (
                existing is not None
                and existing.target_device_id == principal.device_id
                and existing.status == status.value
                and existing.result_json == result
                and existing.error_code == error_code
                and existing.error_message == error_message
            ):
                return existing
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
