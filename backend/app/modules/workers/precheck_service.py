"""Create one stable Worker task per application/product revision."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import re
from uuid import UUID, uuid4

import httpx
from pydantic import SecretStr, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.integrations.douyin_signer.client import DouyinSignerClient
from app.integrations.douyin_signer.pure_client import PureDouyinSigner
from app.integrations.douyin_signer.exceptions import DouyinSignerError
from app.integrations.douyin_signer.schemas import DouyinSignRequest
from app.modules.devices.models import Device
from app.modules.sessions.application_auth import ApplicationAuthenticationError, ApplicationAuthenticator, ApplicationPrincipal
from app.modules.tasks.models import Task
from app.modules.users.models import User
from app.modules.workers.models import DeviceRuntime, DeviceSkillCapability
from app.modules.workers.precheck_contract import PRECHECK_KIND, PrecheckDeliveryAcknowledgement, PrecheckSignInput, PrecheckSubmission, PrecheckTerminal, RpaInventoryReport, mapped_shop_id, supports_category_lookup, supports_full_category_tree, supports_schema_hints, validate_terminal_result
from app.modules.workers.precheck_models import ApplicationWorkerPrecheck, WorkerRpaShopInventory
from app.modules.workers.session_health import merge_session_observations, worker_session_observation


class PrecheckUnavailable(AppError):
    code, message, status_code = "PRECHECK_UNAVAILABLE", "当前没有可用的已授权设备及店铺", 503


class PrecheckNotFound(AppError):
    code, message, status_code = "PRECHECK_NOT_FOUND", "预检任务不存在或未授权", 404


class PrecheckConflict(AppError):
    code, message, status_code = "PRECHECK_CONFLICT", "该商品版本的预检请求或状态不一致", 409


class PrecheckPlatformRetryExhausted(AppError):
    code, message, status_code = "PRECHECK_PLATFORM_RETRY_EXHAUSTED", "没有可更换的授权店铺", 409


class PrecheckInvalidResult(AppError):
    code, message, status_code = "PRECHECK_RESULT_INVALID", "设备预检结果无效", 422


class PrecheckSignerUnavailable(AppError):
    code, message, status_code = "PRECHECK_SIGNER_UNAVAILABLE", "本次预检签名未完成", 503


def _validate_platform_retry(task: Task, terminal_json: SecretStr) -> str:
    """Validate the exact Worker result without persisting or logging it."""
    try:
        encoded = terminal_json.get_secret_value().encode("utf-8")
        if len(encoded) > 8192:
            raise ValueError("retry proof too large")
        terminal = PrecheckTerminal.model_validate_json(encoded)
        if (terminal.status != "failed" or terminal.error_code != "PLATFORM_BUSINESS_REJECTED"
                or not isinstance(terminal.result, dict)
                or terminal.result.get("safe_error_code") != "PLATFORM_BUSINESS_REJECTED"
                or terminal.result.get("error_stage") != "platform"
                or terminal.result.get("platform_code") not in (10004, "10004")):
            raise ValueError("not an eligible rejection")
        validate_terminal_result(terminal.result, success=False, expected=task.input_json,
                                 device_id=task.target_device_id)
        return hashlib.sha256(encoded).hexdigest()
    except (UnicodeError, ValueError, TypeError, KeyError, ValidationError):
        raise PrecheckInvalidResult() from None


def session_snapshot_expired(session: Session, task: Task) -> bool:
    """A queued task must not request the platform with a known-expired snapshot."""
    revision = task.input_json.get("_session_revision")
    local_id = task.input_json.get("local_shop_id")
    platform_id = task.input_json.get("platform_shop_id")
    if not all(isinstance(value, str) and value for value in (revision, local_id, platform_id)):
        return False
    latest = session.execute(select(Task.status, Task.error_code, Task.finished_at, Task.created_at).where(
        Task.target_device_id == task.target_device_id, Task.skill_id == PRECHECK_KIND,
        Task.input_json["local_shop_id"].astext == local_id,
        Task.input_json["platform_shop_id"].astext == platform_id,
        Task.input_json["_session_revision"].astext == revision,
        Task.status == "failed", Task.error_code == "SHOP_SESSION_EXPIRED",
        Task.task_id != task.task_id,
    ).order_by(Task.finished_at.desc().nullslast(), Task.created_at.desc(), Task.task_id.desc()).limit(1)).first()
    known = (("invalid" if latest.status == "failed" else "valid"), latest.finished_at or latest.created_at) if latest else None
    inventory = session.get(WorkerRpaShopInventory, task.target_device_id)
    if inventory is not None:
        for shop in inventory.shops:
            if (shop.get("localShopId"), shop.get("platformShopId"), shop.get("sessionRevision")) == (local_id, platform_id, revision):
                observed = worker_session_observation(shop)
                known = merge_session_observations(known, observed)
                break
    return bool(known and known[0] == "invalid")


def supports_saved_shop_sessions(version: str) -> bool:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    return bool(match and tuple(int(part) for part in match.groups()) >= (0, 5, 2))


class WorkerPrecheckService:
    def __init__(self, session: Session, authenticator: ApplicationAuthenticator):
        self.session = session
        self.authenticator = authenticator

    def _grant(self, principal: ApplicationPrincipal):
        current = self.authenticator.authenticate(principal.grant.client_id, principal.token).grant
        user = self.session.get(User, current.authorized_by_user_id)
        if (current.authorized_by_user_id != principal.grant.authorized_by_user_id or user is None
                or not user.enabled or not user.is_super_account):
            raise ApplicationAuthenticationError()
        if not current.worker_precheck_enabled or not (current.all_precheck_devices or (
                current.device_ids and (current.device_shops or current.all_mapped_shops))):
            raise PrecheckNotFound()
        return current

    @staticmethod
    def _authorized_shop(grant, device_id: UUID, local_shop_id: str, platform_shop_id: str) -> bool:
        if getattr(grant, "all_precheck_devices", False):
            return device_id not in grant.excluded_precheck_devices
        return device_id in grant.device_ids and (device_id in grant.all_mapped_shops or any(
            s.device_id == device_id and s.local_shop_id == local_shop_id and s.platform_shop_id == platform_shop_id
            for s in grant.device_shops
        ))

    @staticmethod
    def _require_allowed_context(grant, data: PrecheckSubmission) -> None:
        limit = grant.precheck_context
        if limit is not None and (limit.product_id, limit.revision) != (
                data.context.product_id, data.context.revision):
            raise PrecheckUnavailable()

    def available_shops(self, principal: ApplicationPrincipal) -> list[dict]:
        """Expose authorized Worker-reported shop identities, never their Sessions."""
        grant = self._grant(principal)
        now = datetime.now(UTC)
        device_scope = (Device.device_id.not_in(grant.excluded_precheck_devices)
                        if grant.all_precheck_devices else Device.device_id.in_(grant.device_ids))
        task_device_scope = (Task.target_device_id.not_in(grant.excluded_precheck_devices)
                             if grant.all_precheck_devices else Task.target_device_id.in_(grant.device_ids))
        rows = self.session.execute(
            select(Device, WorkerRpaShopInventory, DeviceRuntime.worker_version, DeviceSkillCapability.skill_version)
            .join(DeviceRuntime, DeviceRuntime.device_id == Device.device_id)
            .join(WorkerRpaShopInventory, WorkerRpaShopInventory.device_id == Device.device_id)
            .join(DeviceSkillCapability, DeviceSkillCapability.device_id == Device.device_id)
            .where(device_scope, Device.enabled.is_(True), Device.deleted_at.is_(None),
                   DeviceRuntime.connection_status == "online", DeviceRuntime.last_seen_at >= now - timedelta(seconds=90),
                   WorkerRpaShopInventory.available.is_(True),
                   WorkerRpaShopInventory.last_discovered_at >= now - timedelta(minutes=5),
                   DeviceSkillCapability.skill_id == PRECHECK_KIND)
        ).all()
        if not rows:
            return []
        local_key = Task.input_json["local_shop_id"].astext
        platform_key = Task.input_json["platform_shop_id"].astext
        revision_key = Task.input_json["_session_revision"].astext
        latest = self.session.execute(
            select(Task.target_device_id, local_key, platform_key, revision_key, Task.status, Task.error_code)
            .where(task_device_scope, Task.target_device_id.in_([row[0].device_id for row in rows]),
                   Task.skill_id == PRECHECK_KIND, revision_key.is_not(None),
                   Task.status == "failed", Task.error_code == "SHOP_SESSION_EXPIRED")
            .distinct(Task.target_device_id, local_key, platform_key, revision_key)
            .order_by(Task.target_device_id, local_key, platform_key, revision_key,
                      Task.finished_at.desc().nullslast(), Task.created_at.desc(), Task.task_id.desc())
        ).all()
        invalid = {(device_id, local_id, platform_id, revision)
                   for device_id, local_id, platform_id, revision, status, error in latest
                   if status == "failed" and error == "SHOP_SESSION_EXPIRED"}
        invalid_shops = {(device_id, local_id, platform_id) for device_id, local_id, platform_id, _ in invalid}
        found: dict[UUID, dict] = {}
        for device, inventory, worker_version, skill_version in rows:
            if not supports_saved_shop_sessions(worker_version) or not supports_category_lookup(skill_version):
                continue
            for shop in inventory.shops:
                local_id, platform_id = shop.get("localShopId"), shop.get("platformShopId")
                if (shop.get("platform") != "douyin" or shop.get("sessionStored") is not True
                        or not isinstance(local_id, str) or not local_id
                        or not isinstance(platform_id, str) or not platform_id
                        or not self._authorized_shop(grant, device.device_id, local_id, platform_id)):
                    continue
                revision = shop.get("sessionRevision")
                if ((device.device_id, local_id, platform_id, revision) in invalid
                        or (not revision and (device.device_id, local_id, platform_id) in invalid_shops)):
                    continue
                observation = shop.get("sessionStatus")
                if observation == "invalid":
                    continue
                identity = mapped_shop_id(platform_id)
                value = {"shop_id": identity, "display_name": str(shop.get("shopName") or "店铺")[:200],
                         "platform": "douyin", "session_status": "valid" if observation == "valid" else "captured"}
                if identity not in found or value["session_status"] == "valid":
                    found[identity] = value
        return sorted(found.values(), key=lambda value: str(value["shop_id"]))

    def submit(self, principal: ApplicationPrincipal, data: PrecheckSubmission) -> Task:
        grant = self._grant(principal)
        self._require_allowed_context(grant, data)
        # The PostgreSQL transaction lock serializes same-claim creation across
        # server processes without depending on the product's transient attempt.
        lock_key = json.dumps([grant.client_id, data.context.product_id, data.context.revision],
                              ensure_ascii=False, separators=(",", ":"))
        self.session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(lock_key, 0))))
        # Omit new defaults so the hash of already queued schema tasks is unchanged.
        request_data = {"kind": data.kind, "input": data.input.model_dump(mode="json", exclude_defaults=True)}
        if data.delivery == "product":
            request_data["delivery"] = data.delivery
        request_hash = hashlib.sha256(json.dumps(
            request_data, sort_keys=True,
            ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        key = (grant.client_id, data.context.product_id, data.context.revision)
        existing = self.session.get(ApplicationWorkerPrecheck, key)
        bounded_retry = False
        if existing is not None:
            if existing.request_hash != request_hash:
                raise PrecheckConflict()
            task = self.session.get(Task, existing.task_id)
            if task is None or not self._authorized_shop(grant, task.target_device_id,
                    task.input_json["local_shop_id"], task.input_json["platform_shop_id"]):
                raise PrecheckNotFound()
            if data.retry is not None:
                previous = self.session.get(Task, data.retry.previous_task_id)
                context = previous.input_json.get("_precheck_context") if previous is not None else None
                if (data.delivery != "product" or previous is None or previous.skill_id != PRECHECK_KIND
                        or previous.input_json.get("_result_delivery") != "product"
                        or context != {"client_id": grant.client_id, "product_id": data.context.product_id,
                                       "revision": data.context.revision}
                        or not self._authorized_shop(grant, previous.target_device_id,
                            previous.input_json.get("local_shop_id"), previous.input_json.get("platform_shop_id"))):
                    raise PrecheckNotFound()
                digest = _validate_platform_retry(previous, data.retry.terminal_json)
                # Direct delivery precedes the Worker acknowledgement. Preserve
                # the same task until its digest is durable, never dispatch early.
                if previous.task_id == task.task_id and previous.status in ("pending", "running", "lost"):
                    return task
                receipt = previous.result_json if isinstance(previous.result_json, dict) else {}
                recorded = receipt.get("delivery_sha256")
                if (previous.status != "failed" or previous.error_code != "PLATFORM_BUSINESS_REJECTED"
                        or not isinstance(recorded, str) or not hmac.compare_digest(recorded, digest)):
                    raise PrecheckInvalidResult()
                # A repeated acknowledgement for an older attempt can only
                # observe the current assignment; it cannot trigger a new one.
                if previous.task_id != task.task_id:
                    return task
                if data.input.shop_id is not None:
                    raise PrecheckPlatformRetryExhausted()
                bounded_retry = True
            else:
                # Preserve the existing explicit session-expiry handling.
                if not (task.status == "failed" and task.error_code == "SHOP_SESSION_EXPIRED"
                        and task.input_json.get("_result_delivery") == "product"
                        and task.input_json.get("_session_revision")):
                    return task
                bounded_retry = task.input_json.get("_platform_retry_chain") is True
        elif data.retry is not None:
            raise PrecheckNotFound()

        # Serialize this short selection/insert transaction so concurrent
        # submissions observe each other's latest shop assignment.
        self.session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended("worker-precheck-shop-rotation", 0))))
        now = datetime.now(UTC)
        device_scope = (Device.device_id.not_in(grant.excluded_precheck_devices)
                        if grant.all_precheck_devices else Device.device_id.in_(grant.device_ids))
        task_device_scope = (Task.target_device_id.not_in(grant.excluded_precheck_devices)
                             if grant.all_precheck_devices else Task.target_device_id.in_(grant.device_ids))
        rows = self.session.execute(
            select(Device, WorkerRpaShopInventory, DeviceRuntime.worker_version, DeviceSkillCapability.skill_version)
            .join(DeviceRuntime, DeviceRuntime.device_id == Device.device_id)
            .join(WorkerRpaShopInventory, WorkerRpaShopInventory.device_id == Device.device_id)
            .join(DeviceSkillCapability, DeviceSkillCapability.device_id == Device.device_id)
            .where(device_scope, Device.enabled.is_(True), Device.deleted_at.is_(None),
                   DeviceRuntime.connection_status == "online", DeviceRuntime.last_seen_at >= now - timedelta(seconds=90),
                   WorkerRpaShopInventory.available.is_(True),
                   WorkerRpaShopInventory.last_discovered_at >= now - timedelta(minutes=5),
                   DeviceSkillCapability.skill_id == PRECHECK_KIND)
        ).all()
        # Prefer different platform shops across the devices available to this
        # application, while still balancing the total queue on each device.
        platform_key = Task.input_json["platform_shop_id"].astext
        active_by_shop = dict(self.session.execute(
            select(platform_key, func.count())
            .where(task_device_scope, Task.skill_id == PRECHECK_KIND,
                   Task.status.in_(("pending", "running")))
            .group_by(platform_key)
        ).all())
        local_key = Task.input_json["local_shop_id"].astext
        revision_key = Task.input_json["_session_revision"].astext
        # Compute the queue state once, rather than issuing two queries for
        # every store while holding the short assignment lock. A device may
        # have many stores, and needs five stores with three tasks each to
        # actually reach its execution capacity.
        device_loads = dict(self.session.execute(
            select(Task.target_device_id, func.count())
            .where(task_device_scope, Task.status.in_(("pending", "running")))
            .group_by(Task.target_device_id)
        ).all())
        active_pairs = {(device_id, local_id): count for device_id, local_id, count in self.session.execute(
            select(Task.target_device_id, local_key, func.count())
            .where(task_device_scope, Task.skill_id == PRECHECK_KIND,
                   Task.status.in_(("pending", "running")), local_key.is_not(None))
            .group_by(Task.target_device_id, local_key)
        ).all()}
        active_shops_per_device: dict[UUID, int] = {}
        for device_id, _ in active_pairs:
            active_shops_per_device[device_id] = active_shops_per_device.get(device_id, 0) + 1
        last_by_pair = {(device_id, local_id): assigned for device_id, local_id, assigned in self.session.execute(
            select(Task.target_device_id, local_key, func.max(Task.created_at))
            .where(task_device_scope, Task.skill_id == PRECHECK_KIND, local_key.is_not(None))
            .group_by(Task.target_device_id, local_key)
        ).all()}
        latest = self.session.execute(
            select(Task.target_device_id, local_key, platform_key, revision_key, Task.status, Task.error_code,
                   Task.finished_at, Task.created_at)
            .where(task_device_scope, Task.skill_id == PRECHECK_KIND,
                   Task.status == "failed", Task.error_code == "SHOP_SESSION_EXPIRED",
                   revision_key.is_not(None))
            .distinct(Task.target_device_id, local_key, platform_key, revision_key)
            .order_by(Task.target_device_id, local_key, platform_key, revision_key,
                      Task.finished_at.desc().nullslast(), Task.created_at.desc(), Task.task_id.desc())
        ).all()
        observations = {(device_id, local_id, platform_id, revision):
                        ("invalid" if status == "failed" else "valid", finished or created)
                        for device_id, local_id, platform_id, revision, status, error, finished, created in latest}
        for device, inventory, _, _ in rows:
            for shop in inventory.shops:
                observed = worker_session_observation(shop)
                key = (device.device_id, shop.get("localShopId"), shop.get("platformShopId"), shop.get("sessionRevision"))
                merged = merge_session_observations(observations.get(key), observed)
                if merged:
                    observations[key] = merged
        invalid_snapshots = {key for key, (status, _) in observations.items() if status == "invalid"}
        invalid_shops = {(device_id, local_id, platform_id)
                         for device_id, local_id, platform_id, _ in invalid_snapshots}
        # For this product, retry a different shop, not the same platform shop
        # through another computer. A newly saved snapshot on the original
        # device makes that shop eligible again.
        avoided_shops: set[str] = set()
        if existing is not None:
            context_key = Task.input_json["_precheck_context"]
            failures = self.session.scalars(select(Task).where(
                Task.skill_id == PRECHECK_KIND, Task.status == "failed", Task.error_code == "SHOP_SESSION_EXPIRED",
                context_key["client_id"].astext == grant.client_id,
                context_key["product_id"].astext == data.context.product_id,
                context_key["revision"].astext == str(data.context.revision),
            )).all()
            for failure in failures:
                local_id = failure.input_json.get("local_shop_id")
                platform_id = failure.input_json.get("platform_shop_id")
                old_revision = failure.input_json.get("_session_revision")
                refreshed = any(
                    device.device_id == failure.target_device_id and any(
                        shop.get("localShopId") == local_id and shop.get("platformShopId") == platform_id
                        and shop.get("sessionStored") is True
                        and isinstance(shop.get("sessionRevision"), str)
                        and re.fullmatch(r"[0-9a-f]{64}", shop["sessionRevision"])
                        and shop["sessionRevision"] != old_revision
                        and (device.device_id, local_id, platform_id, shop["sessionRevision"]) not in invalid_snapshots
                        for shop in inventory.shops)
                    for device, inventory, _, _ in rows)
                if not refreshed and isinstance(platform_id, str):
                    avoided_shops.add(platform_id)
        if bounded_retry:
            context_key = Task.input_json["_precheck_context"]
            attempted = set(self.session.scalars(select(platform_key).where(
                Task.skill_id == PRECHECK_KIND,
                context_key["client_id"].astext == grant.client_id,
                context_key["product_id"].astext == data.context.product_id,
                context_key["revision"].astext == str(data.context.revision),
                platform_key.is_not(None),
            )).all())
            attempted = {shop for shop in attempted if isinstance(shop, str) and shop}
            if len(attempted) >= 3:
                raise PrecheckPlatformRetryExhausted()
            avoided_shops.update(attempted)
        choices = []
        for device, inventory, worker_version, skill_version in rows:
            if (not supports_saved_shop_sessions(worker_version)
                    or (data.input.operation != "schema" and not supports_category_lookup(skill_version))
                    or ((data.input.full_category_tree or data.input.require_schema_metadata)
                        and not supports_full_category_tree(skill_version))
                    or (data.input.require_schema_hints and not supports_schema_hints(skill_version))):
                continue
            for shop in inventory.shops:
                local_id, platform_id = shop.get("localShopId"), shop.get("platformShopId")
                session_revision = shop.get("sessionRevision")
                if not isinstance(session_revision, str) or not re.fullmatch(r"[0-9a-f]{64}", session_revision):
                    session_revision = None
                if (shop.get("platform") != "douyin" or shop.get("sessionStored") is not True or not isinstance(local_id, str)
                        or not isinstance(platform_id, str)
                        or (data.input.shop_id is not None and mapped_shop_id(platform_id) != data.input.shop_id)
                        or not self._authorized_shop(grant, device.device_id, local_id, platform_id)
                        or platform_id in avoided_shops
                        or (session_revision is None and (device.device_id, local_id, platform_id) in invalid_shops)
                        or (device.device_id, local_id, platform_id, session_revision) in invalid_snapshots):
                    continue
                count = active_pairs.get((device.device_id, local_id), 0)
                shop_count = active_shops_per_device.get(device.device_id, 0)
                # First use up to five different shops, then fill each to
                # three. Once all are full, start the next rotation; the
                # execution-side limits remain authoritative.
                if shop_count < 5:
                    fill_rank = 0 if count == 0 else 1 if count < 3 else 2
                else:
                    fill_rank = 0 if 0 < count < 3 else 1 if count == 0 else 2
                choices.append((device_loads.get(device.device_id, 0), fill_rank,
                                active_by_shop.get(platform_id, 0),
                                last_by_pair.get((device.device_id, local_id)) or datetime.min.replace(tzinfo=UTC),
                                str(device.device_id), local_id, platform_id, session_revision, device))
        if not choices:
            if bounded_retry:
                raise PrecheckPlatformRetryExhausted()
            raise PrecheckUnavailable()
        _, _, _, _, _, local_id, platform_id, session_revision, device = min(choices, key=lambda row: row[:6])
        # Re-read protected grant immediately before writing, including the
        # exact chosen local shop; revocation never broadens an old grant.
        grant = self._grant(principal)
        self._require_allowed_context(grant, data)
        if not self._authorized_shop(grant, device.device_id, local_id, platform_id):
            raise PrecheckNotFound()
        task = Task(
            task_id=uuid4(), team_id=device.team_id, created_by_user_id=grant.authorized_by_user_id,
            target_device_id=device.device_id, skill_id=PRECHECK_KIND,
            execution_display_name="商品类目预检", status="pending",
            # PostgreSQL now() is the transaction start and can precede a
            # waiting selection lock; use actual assignment time instead.
            created_at=self.session.scalar(select(func.clock_timestamp())),
            input_json={"category_id": data.input.category_id, "title": data.input.title,
                        "local_shop_id": local_id, "platform_shop_id": platform_id,
                        **({"operation": data.input.operation} if data.input.operation != "schema" else {}),
                        **({"_full_category_tree": True} if data.input.full_category_tree else {}),
                        **({"_require_schema_metadata": True} if data.input.require_schema_metadata else {}),
                        **({"_require_schema_hints": True} if data.input.require_schema_hints else {}),
                        **({"image_url": data.input.image_url} if data.input.image_url is not None else {}),
                        **({"_session_revision": session_revision} if session_revision else {}),
                        **({"_platform_retry_chain": True} if bounded_retry else {}),
                        "_precheck_context": {"client_id": grant.client_id,
                            "product_id": data.context.product_id, "revision": data.context.revision},
                        **({"_result_delivery": "product"} if data.delivery == "product" else {})},
        )
        self.session.add(task)
        self.session.flush()
        if existing is None:
            self.session.add(ApplicationWorkerPrecheck(client_id=grant.client_id,
                product_id=data.context.product_id, revision=data.context.revision,
                request_hash=request_hash, task_id=task.task_id))
        else:
            existing.task_id = task.task_id
        self.session.commit()
        return task

    def get(self, principal: ApplicationPrincipal, task_id: UUID) -> Task:
        grant = self._grant(principal)
        record = self.session.scalar(select(ApplicationWorkerPrecheck).where(
            ApplicationWorkerPrecheck.client_id == grant.client_id,
            ApplicationWorkerPrecheck.task_id == task_id,
        ))
        task = self.session.get(Task, task_id) if record else None
        if task is None or not self._authorized_shop(grant, task.target_device_id,
                task.input_json["local_shop_id"], task.input_json["platform_shop_id"]):
            raise PrecheckNotFound()
        return task


def save_rpa_inventory(session: Session, device_id: UUID, data: RpaInventoryReport) -> None:
    device = session.get(Device, device_id)
    if device is None or not device.enabled or device.deleted_at is not None:
        raise PrecheckNotFound()
    inventory = session.scalar(select(WorkerRpaShopInventory).where(
        WorkerRpaShopInventory.device_id == device_id).with_for_update())
    now = datetime.now(UTC)
    if inventory is None:
        inventory = WorkerRpaShopInventory(device_id=device_id, available=False,
                                           shops=[], last_discovered_at=now)
        session.add(inventory)
    inventory.available = data.available
    inventory.last_discovered_at = now
    inventory.updated_at = now
    if data.available:
        previous = {}
        if inventory.installation_id == data.installation_id:
            previous = {(shop.get("localShopId"), shop.get("platformShopId"), shop.get("sessionRevision")): shop
                        for shop in inventory.shops}
        shops = []
        for shop in data.shops:
            row = shop.model_dump(mode="json", by_alias=True)
            checked_at = shop.session_checked_at
            if checked_at and checked_at > now + timedelta(minutes=5):
                # A bad device clock must not make its entire inventory or
                # unrelated prechecks unavailable.
                checked_at = None
                row["sessionStatus"], row["sessionCheckedAt"] = None, None
            old = previous.get((shop.local_shop_id, shop.platform_shop_id, shop.session_revision))
            old_observation = worker_session_observation(old, now=now) if old else None
            if old_observation and (checked_at is None or old_observation[1] > checked_at):
                row["sessionStatus"], row["sessionCheckedAt"] = old_observation[0], old_observation[1].isoformat()
            shops.append(row)
        inventory.installation_id = data.installation_id
        inventory.shops = shops
    session.commit()


def accept_precheck_terminal(session: Session, device_id: UUID, task_id: UUID, data: PrecheckTerminal) -> Task:
    record = session.scalar(select(ApplicationWorkerPrecheck).where(
        ApplicationWorkerPrecheck.task_id == task_id).with_for_update())
    task = session.scalar(select(Task).where(Task.task_id == task_id).with_for_update())
    if (record is None or task is None or task.target_device_id != device_id or task.skill_id != PRECHECK_KIND
            or task.input_json.get("_result_delivery") == "product"):
        raise PrecheckNotFound()
    if data.result is None:
        raise PrecheckInvalidResult()
    try:
        validate_terminal_result(data.result, success=data.status == "success", expected=task.input_json, device_id=device_id)
    except (ValueError, TypeError, KeyError):
        raise PrecheckInvalidResult() from None
    safe_code = None if data.status == "success" else data.result["safe_error_code"]
    safe_message = None if data.status == "success" else "设备预检未完成"
    if task.status in ("success", "failed"):
        if task.status == data.status and task.result_json == data.result and task.error_code == safe_code:
            return task
        raise PrecheckConflict()
    if task.status not in ("running", "lost"):
        raise PrecheckConflict()
    newer = session.scalar(select(ApplicationWorkerPrecheck.task_id).where(
        ApplicationWorkerPrecheck.client_id == record.client_id,
        ApplicationWorkerPrecheck.product_id == record.product_id,
        ApplicationWorkerPrecheck.revision > record.revision).limit(1))
    if newer is not None:
        raise PrecheckConflict()
    task.status = data.status
    task.result_json = data.result
    task.error_code = safe_code
    task.error_message = safe_message
    task.lease_until = None
    task.finished_at = datetime.now(UTC)
    session.commit()
    return task


def product_delivery_context(session: Session, authenticator: ApplicationAuthenticator,
                             device_id: UUID, task_id: UUID, *, protocol_v2: bool = False,
                             protocol_v3: bool = False, protocol_v4: bool = False) -> dict:
    """Authenticate the assigned Worker and describe only its own direct delivery."""
    record = session.scalar(select(ApplicationWorkerPrecheck).where(ApplicationWorkerPrecheck.task_id == task_id))
    task = session.get(Task, task_id)
    device = session.get(Device, device_id)
    if (task is None or task.target_device_id != device_id or task.skill_id != PRECHECK_KIND
            or task.input_json.get("_result_delivery") != "product"
            or task.status not in ("running", "lost", "success", "failed")
            or device is None or not device.enabled or device.deleted_at is not None):
        raise PrecheckNotFound()
    superseded = False
    if record is None:
        # An old Worker's acknowledgement may have succeeded just before its
        # network response was lost. Its identical replay must remain harmless
        # after the product revision has been assigned to a replacement task.
        context = task.input_json.get("_precheck_context")
        receipt = task.result_json if isinstance(task.result_json, dict) else {}
        replayable = (task.error_code == "SHOP_SESSION_EXPIRED" or
                      (protocol_v4 and task.error_code == "PLATFORM_BUSINESS_REJECTED"))
        if (not protocol_v2 or task.status != "failed" or not replayable
                or not isinstance(context, dict) or not isinstance(receipt.get("delivery_sha256"), str)):
            raise PrecheckNotFound()
        record = session.get(ApplicationWorkerPrecheck,
            (context.get("client_id"), context.get("product_id"), context.get("revision")))
        if record is None or record.task_id == task_id:
            raise PrecheckNotFound()
        superseded = True
    grant = authenticator.current_grant(record.client_id)
    user = session.get(User, grant.authorized_by_user_id)
    if (not grant.worker_precheck_enabled or user is None or not user.enabled or not user.is_super_account
            or not WorkerPrecheckService._authorized_shop(grant, device_id,
                task.input_json["local_shop_id"], task.input_json["platform_shop_id"])):
        raise PrecheckNotFound()
    result = {"task_id": str(task_id), "client_id": record.client_id, "product_id": record.product_id,
              "revision": record.revision, "device_id": str(device_id),
              "category_id": task.input_json["category_id"], "local_shop_id": task.input_json["local_shop_id"],
              "platform_shop_id": task.input_json["platform_shop_id"]}
    if protocol_v2:
        revision = task.input_json.get("_session_revision")
        result.update({"session_retry_supported": bool(isinstance(revision, str)
                            and re.fullmatch(r"[0-9a-f]{64}", revision)) and not superseded,
                       "superseded": superseded,
                       "receipt_sha256": task.result_json.get("delivery_sha256") if superseded else None})
    if protocol_v3:
        result["operation"] = task.input_json.get("operation", "schema")
    if protocol_v4:
        result["platform_retry_supported"] = not superseded
    return result


def acknowledge_product_delivery(session: Session, device_id: UUID, task_id: UUID,
                                 data: PrecheckDeliveryAcknowledgement) -> Task:
    task = session.scalar(select(Task).where(Task.task_id == task_id).with_for_update())
    if (task is None or task.target_device_id != device_id or task.skill_id != PRECHECK_KIND
            or task.input_json.get("_result_delivery") != "product"):
        raise PrecheckNotFound()
    receipt = {"delivery_sha256": data.payload_sha256}
    if task.status in ("success", "failed"):
        if task.status == data.status and task.result_json == receipt and task.error_code == data.error_code:
            return task
        raise PrecheckConflict()
    record = session.scalar(select(ApplicationWorkerPrecheck).where(
        ApplicationWorkerPrecheck.task_id == task_id).with_for_update())
    if record is None:
        raise PrecheckNotFound()
    if task.status not in ("running", "lost"):
        raise PrecheckConflict()
    task.status = data.status
    task.result_json = receipt
    task.error_code = data.error_code
    task.error_message = "设备预检未完成" if data.status == "failed" else None
    task.lease_until = None
    task.finished_at = datetime.now(UTC)
    session.commit()
    return task


def _require_current_category_capability(session: Session, device_id: UUID, *, require_hints: bool = False) -> None:
    capability = session.get(DeviceSkillCapability, (device_id, PRECHECK_KIND))
    supports = supports_schema_hints if require_hints else supports_full_category_tree
    if capability is None or not supports(capability.skill_version):
        raise PrecheckUnavailable()


def _tree_display_all(session: Session, device_id: UUID, task: Task) -> str:
    """A full-tree request may never silently fall back to a partial tree."""
    if task.input_json.get("_full_category_tree") is not True:
        return "0"
    _require_current_category_capability(session, device_id)
    return "1"


def sign_current_precheck(session: Session, authenticator: ApplicationAuthenticator,
                          signer: DouyinSignerClient | PureDouyinSigner, device_id: UUID, task_id: UUID,
                          data: PrecheckSignInput) -> dict[str, str]:
    """Sign only the frozen category task; no caller-selected host or path."""
    record = session.scalar(select(ApplicationWorkerPrecheck).where(ApplicationWorkerPrecheck.task_id == task_id))
    task = session.get(Task, task_id)
    if (record is None or task is None or task.target_device_id != device_id or task.skill_id != PRECHECK_KIND
            or task.status != "running" or task.lease_until is None or task.lease_until <= datetime.now(UTC)):
        raise PrecheckNotFound()
    grant = authenticator.current_grant(record.client_id)
    user = session.get(User, grant.authorized_by_user_id)
    if (not grant.worker_precheck_enabled or user is None or not user.enabled or not user.is_super_account
            or not WorkerPrecheckService._authorized_shop(grant, device_id,
                task.input_json["local_shop_id"], task.input_json["platform_shop_id"])):
        raise PrecheckNotFound()
    cookie = data.cookie.get_secret_value()
    pairs = {}
    for pair in cookie.split(";"):
        key, separator, value = pair.strip().partition("=")
        if separator:
            pairs[key] = value
    operation = task.input_json.get("operation", "schema")
    if operation not in {"schema", "tree", "search", "predict"}:
        raise PrecheckInvalidResult()
    if operation == "schema" and (task.input_json.get("_require_schema_metadata") is True
                                   or task.input_json.get("_require_schema_hints") is True):
        _require_current_category_capability(session, device_id,
            require_hints=task.input_json.get("_require_schema_hints") is True)
    lid = {"schema": "029388877158", "tree": "197362053948",
           "search": "165756507732", "predict": "209821032275"}[operation]
    params = {"appid": "1", "_bid": "ffa_goods", "_lid": lid}
    if pairs.get("s_v_web_id"):
        params.update({"verifyFp": pairs["s_v_web_id"], "fp": pairs["s_v_web_id"]})
    if pairs.get("msToken"):
        params["msToken"] = pairs["msToken"]
    if operation == "schema":
        path, method = "/product/tproduct/getSchema", "POST"
        payload = {
            "context": {"feature": {"session_publish_id": "helper_" + uuid4().hex,
                                     "image_smart_publish_info": "[]"},
                        "operation_type": "select_normal,normal", "category_id": task.input_json["category_id"], "ability": []},
            "model": {"pic": {"value": []}, "title": {"value": task.input_json["title"]},
                      "goods_category_appeal": {"value": False}},
            "appid": 1, "_bid": "ffa_goods", "_lid": lid,
        }
    elif operation == "predict":
        path, method = "/product/tproduct/predictCategoryN", "POST"
        payload = {"scene": "predict_by_title_and_img", "pic": [{"url": task.input_json["image_url"]}],
                   "title": task.input_json["title"], "publish_id": "helper_" + uuid4().hex,
                   "is_auction_or_mass": False, "appid": 1, "_bid": "ffa_goods", "_lid": "209821037550"}
    elif operation == "tree":
        path, method, payload = "/product/tproduct/categoryOptionsN", "GET", None
        params.update({"cid": task.input_json["category_id"], "display_all": _tree_display_all(session, device_id, task)})
    else:
        path, method, payload = "/product/tproduct/searchCategoryN", "GET", None
        params.update({"key": task.input_json["title"], "search_type": "1"})
    body = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) if payload is not None else "")
    url = httpx.URL("https://fxg.jinritemai.com" + path, params=params)
    try:
        for _ in range(2):
            signed = signer.sign(DouyinSignRequest(
                host="fxg.jinritemai.com", full_url=str(url), method=method, cookie=SecretStr(cookie),
                user_agent=data.user_agent, referer="https://fxg.jinritemai.com/ffa/g/create",
                body=SecretStr(body) if payload is not None else None,
                ms_token=SecretStr(params["msToken"]) if "msToken" in params else None,
                aid=4272, page_id=6241,
            ))
            generated = signed.ms_token.get_secret_value() if signed.ms_token else None
            if generated and "msToken" not in params:
                params["msToken"] = generated
                url = url.copy_add_param("msToken", generated)
                continue
            return {"url": str(url.copy_add_param("a_bogus", signed.a_bogus.get_secret_value())), "body": body}
    except DouyinSignerError:
        raise PrecheckSignerUnavailable() from None
    raise PrecheckSignerUnavailable()
