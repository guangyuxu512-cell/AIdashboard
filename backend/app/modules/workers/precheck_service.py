"""Create one stable Worker task per application/product revision."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
import re
from uuid import UUID, uuid4

import httpx
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.integrations.douyin_signer.client import DouyinSignerClient
from app.integrations.douyin_signer.exceptions import DouyinSignerError
from app.integrations.douyin_signer.schemas import DouyinSignRequest
from app.modules.devices.models import Device
from app.modules.sessions.application_auth import ApplicationAuthenticationError, ApplicationAuthenticator, ApplicationPrincipal
from app.modules.tasks.models import Task
from app.modules.users.models import User
from app.modules.workers.models import DeviceRuntime, DeviceSkillCapability
from app.modules.workers.precheck_contract import PRECHECK_KIND, PrecheckDeliveryAcknowledgement, PrecheckSignInput, PrecheckSubmission, PrecheckTerminal, RpaInventoryReport, validate_terminal_result
from app.modules.workers.precheck_models import ApplicationWorkerPrecheck, WorkerRpaShopInventory


class PrecheckUnavailable(AppError):
    code, message, status_code = "PRECHECK_UNAVAILABLE", "当前没有可用的已授权设备及店铺", 503


class PrecheckNotFound(AppError):
    code, message, status_code = "PRECHECK_NOT_FOUND", "预检任务不存在或未授权", 404


class PrecheckConflict(AppError):
    code, message, status_code = "PRECHECK_CONFLICT", "该商品版本的预检请求或状态不一致", 409


class PrecheckInvalidResult(AppError):
    code, message, status_code = "PRECHECK_RESULT_INVALID", "设备预检结果无效", 422


class PrecheckSignerUnavailable(AppError):
    code, message, status_code = "PRECHECK_SIGNER_UNAVAILABLE", "本次预检签名未完成", 503


def session_snapshot_expired(session: Session, task: Task) -> bool:
    """A queued task must not request the platform with a known-expired snapshot."""
    revision = task.input_json.get("_session_revision")
    local_id = task.input_json.get("local_shop_id")
    platform_id = task.input_json.get("platform_shop_id")
    if not all(isinstance(value, str) and value for value in (revision, local_id, platform_id)):
        return False
    latest = session.execute(select(Task.status, Task.error_code).where(
        Task.target_device_id == task.target_device_id, Task.skill_id == PRECHECK_KIND,
        Task.input_json["local_shop_id"].astext == local_id,
        Task.input_json["platform_shop_id"].astext == platform_id,
        Task.input_json["_session_revision"].astext == revision,
        Task.status.in_(("success", "failed")), Task.task_id != task.task_id,
    ).order_by(Task.finished_at.desc().nullslast(), Task.created_at.desc(), Task.task_id.desc()).limit(1)).first()
    return bool(latest and latest.status == "failed" and latest.error_code == "SHOP_SESSION_EXPIRED")


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
        if not current.worker_precheck_enabled or not current.device_ids or not (current.device_shops or current.all_mapped_shops):
            raise PrecheckNotFound()
        return current

    @staticmethod
    def _authorized_shop(grant, device_id: UUID, local_shop_id: str, platform_shop_id: str) -> bool:
        return device_id in grant.device_ids and (device_id in grant.all_mapped_shops or any(
            s.device_id == device_id and s.local_shop_id == local_shop_id and s.platform_shop_id == platform_shop_id
            for s in grant.device_shops
        ))

    def submit(self, principal: ApplicationPrincipal, data: PrecheckSubmission) -> Task:
        grant = self._grant(principal)
        # The PostgreSQL transaction lock serializes same-claim creation across
        # server processes without depending on the product's transient attempt.
        lock_key = json.dumps([grant.client_id, data.context.product_id, data.context.revision],
                              ensure_ascii=False, separators=(",", ":"))
        self.session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(lock_key, 0))))
        request_data = {"kind": data.kind, "input": data.input.model_dump()}
        if data.delivery == "product":
            request_data["delivery"] = data.delivery
        request_hash = hashlib.sha256(json.dumps(
            request_data, sort_keys=True,
            ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        key = (grant.client_id, data.context.product_id, data.context.revision)
        existing = self.session.get(ApplicationWorkerPrecheck, key)
        if existing is not None:
            if existing.request_hash != request_hash:
                raise PrecheckConflict()
            task = self.session.get(Task, existing.task_id)
            if task is None or not self._authorized_shop(grant, task.target_device_id,
                    task.input_json["local_shop_id"], task.input_json["platform_shop_id"]):
                raise PrecheckNotFound()
            # A product-queue retry may move on only after the previous
            # snapshot was explicitly rejected as logged out. Other failures
            # keep the existing idempotent result and are never reclassified.
            if not (task.status == "failed" and task.error_code == "SHOP_SESSION_EXPIRED"
                    and task.input_json.get("_result_delivery") == "product"
                    and task.input_json.get("_session_revision")):
                return task

        # Serialize this short selection/insert transaction so concurrent
        # submissions observe each other's latest shop assignment.
        self.session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended("worker-precheck-shop-rotation", 0))))
        now = datetime.now(UTC)
        rows = self.session.execute(
            select(Device, WorkerRpaShopInventory, DeviceRuntime.worker_version)
            .join(DeviceRuntime, DeviceRuntime.device_id == Device.device_id)
            .join(WorkerRpaShopInventory, WorkerRpaShopInventory.device_id == Device.device_id)
            .join(DeviceSkillCapability, DeviceSkillCapability.device_id == Device.device_id)
            .where(Device.device_id.in_(grant.device_ids), Device.enabled.is_(True), Device.deleted_at.is_(None),
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
            .where(Task.target_device_id.in_(grant.device_ids), Task.skill_id == PRECHECK_KIND,
                   Task.status.in_(("pending", "running")))
            .group_by(platform_key)
        ).all())
        local_key = Task.input_json["local_shop_id"].astext
        revision_key = Task.input_json["_session_revision"].astext
        latest = self.session.execute(
            select(Task.target_device_id, local_key, platform_key, revision_key, Task.status, Task.error_code)
            .where(Task.target_device_id.in_(grant.device_ids), Task.skill_id == PRECHECK_KIND,
                   Task.status.in_(("success", "failed")), revision_key.is_not(None))
            .distinct(Task.target_device_id, local_key, platform_key, revision_key)
            .order_by(Task.target_device_id, local_key, platform_key, revision_key,
                      Task.finished_at.desc().nullslast(), Task.created_at.desc(), Task.task_id.desc())
        ).all()
        invalid_snapshots = {(device_id, local_id, platform_id, revision)
                             for device_id, local_id, platform_id, revision, status, error in latest
                             if status == "failed" and error == "SHOP_SESSION_EXPIRED"}
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
                    for device, inventory, _ in rows)
                if not refreshed and isinstance(platform_id, str):
                    avoided_shops.add(platform_id)
        choices = []
        for device, inventory, worker_version in rows:
            if not supports_saved_shop_sessions(worker_version):
                continue
            for shop in inventory.shops:
                local_id, platform_id = shop.get("localShopId"), shop.get("platformShopId")
                session_revision = shop.get("sessionRevision")
                if not isinstance(session_revision, str) or not re.fullmatch(r"[0-9a-f]{64}", session_revision):
                    session_revision = None
                if (shop.get("platform") != "douyin" or shop.get("sessionStored") is not True or not isinstance(local_id, str)
                        or not isinstance(platform_id, str)
                        or not self._authorized_shop(grant, device.device_id, local_id, platform_id)
                        or platform_id in avoided_shops
                        or (session_revision is None and (device.device_id, local_id, platform_id) in invalid_shops)
                        or (device.device_id, local_id, platform_id, session_revision) in invalid_snapshots):
                    continue
                pending = self.session.scalar(select(func.count()).select_from(Task).where(
                    Task.target_device_id == device.device_id, Task.status.in_(("pending", "running")),
                )) or 0
                last_assigned = self.session.scalar(select(func.max(Task.created_at)).where(
                    Task.target_device_id == device.device_id, Task.skill_id == PRECHECK_KIND,
                    Task.input_json["local_shop_id"].astext == local_id,
                ))
                choices.append((pending, active_by_shop.get(platform_id, 0),
                                last_assigned or datetime.min.replace(tzinfo=UTC),
                                str(device.device_id), local_id, platform_id, session_revision, device))
        if not choices:
            raise PrecheckUnavailable()
        _, _, _, _, local_id, platform_id, session_revision, device = min(choices, key=lambda row: row[:5])
        # Re-read protected grant immediately before writing, including the
        # exact chosen local shop; revocation never broadens an old grant.
        grant = self._grant(principal)
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
                        **({"_session_revision": session_revision} if session_revision else {}),
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
        inventory.installation_id = data.installation_id
        inventory.shops = [shop.model_dump(by_alias=True) for shop in data.shops]
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
                             device_id: UUID, task_id: UUID, *, protocol_v2: bool = False) -> dict:
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
        if (not protocol_v2 or task.status != "failed" or task.error_code != "SHOP_SESSION_EXPIRED"
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


def sign_current_precheck(session: Session, authenticator: ApplicationAuthenticator,
                          signer: DouyinSignerClient, device_id: UUID, task_id: UUID,
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
    params = {"appid": "1", "_bid": "ffa_goods", "_lid": "029388877158"}
    if pairs.get("s_v_web_id"):
        params.update({"verifyFp": pairs["s_v_web_id"], "fp": pairs["s_v_web_id"]})
    if pairs.get("msToken"):
        params["msToken"] = pairs["msToken"]
    body = json.dumps({
        "context": {"feature": {"session_publish_id": "helper_" + uuid4().hex,
                                 "image_smart_publish_info": "[]"},
                    "operation_type": "select_normal,normal", "category_id": task.input_json["category_id"], "ability": []},
        "model": {"pic": {"value": []}, "title": {"value": task.input_json["title"]},
                  "goods_category_appeal": {"value": False}},
        "appid": 1, "_bid": "ffa_goods", "_lid": "029388877158",
    }, ensure_ascii=False, separators=(",", ":"))
    url = httpx.URL("https://fxg.jinritemai.com/product/tproduct/getSchema", params=params)
    try:
        for _ in range(2):
            signed = signer.sign(DouyinSignRequest(
                host="fxg.jinritemai.com", full_url=str(url), method="POST", cookie=SecretStr(cookie),
                user_agent=data.user_agent, referer="https://fxg.jinritemai.com/ffa/g/create",
                body=SecretStr(body), ms_token=SecretStr(params["msToken"]) if "msToken" in params else None,
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
