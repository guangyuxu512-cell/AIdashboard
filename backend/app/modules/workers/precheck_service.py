"""Create one stable Worker task per application/product revision."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
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
from app.modules.workers.precheck_contract import PRECHECK_KIND, PrecheckSignInput, PrecheckSubmission, PrecheckTerminal, RpaInventoryReport, validate_terminal_result
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
        request_hash = hashlib.sha256(json.dumps(
            {"kind": data.kind, "input": data.input.model_dump()}, sort_keys=True,
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
            return task

        # Serialize this short selection/insert transaction so concurrent
        # submissions observe each other's latest shop assignment.
        self.session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended("worker-precheck-shop-rotation", 0))))
        now = datetime.now(UTC)
        rows = self.session.execute(
            select(Device, WorkerRpaShopInventory)
            .join(DeviceRuntime, DeviceRuntime.device_id == Device.device_id)
            .join(WorkerRpaShopInventory, WorkerRpaShopInventory.device_id == Device.device_id)
            .join(DeviceSkillCapability, DeviceSkillCapability.device_id == Device.device_id)
            .where(Device.device_id.in_(grant.device_ids), Device.enabled.is_(True), Device.deleted_at.is_(None),
                   DeviceRuntime.connection_status == "online", DeviceRuntime.last_seen_at >= now - timedelta(seconds=90),
                   WorkerRpaShopInventory.available.is_(True),
                   WorkerRpaShopInventory.last_discovered_at >= now - timedelta(minutes=5),
                   DeviceSkillCapability.skill_id == PRECHECK_KIND)
        ).all()
        choices = []
        for device, inventory in rows:
            for shop in inventory.shops:
                local_id, platform_id = shop.get("localShopId"), shop.get("platformShopId")
                if (shop.get("platform") != "douyin" or shop.get("browserOpen") is not True or not isinstance(local_id, str)
                        or not isinstance(platform_id, str)
                        or not self._authorized_shop(grant, device.device_id, local_id, platform_id)):
                    continue
                pending = self.session.scalar(select(func.count()).select_from(Task).where(
                    Task.target_device_id == device.device_id, Task.status.in_(("pending", "running")),
                )) or 0
                last_assigned = self.session.scalar(select(func.max(Task.created_at)).where(
                    Task.target_device_id == device.device_id, Task.skill_id == PRECHECK_KIND,
                    Task.input_json["local_shop_id"].astext == local_id,
                ))
                choices.append((pending, last_assigned or datetime.min.replace(tzinfo=UTC),
                                str(device.device_id), local_id, platform_id, device))
        if not choices:
            raise PrecheckUnavailable()
        _, _, _, local_id, platform_id, device = min(choices, key=lambda row: row[:4])
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
                        "local_shop_id": local_id, "platform_shop_id": platform_id},
        )
        self.session.add(task)
        self.session.flush()
        self.session.add(ApplicationWorkerPrecheck(client_id=grant.client_id,
            product_id=data.context.product_id, revision=data.context.revision,
            request_hash=request_hash, task_id=task.task_id))
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
    if record is None or task is None or task.target_device_id != device_id or task.skill_id != PRECHECK_KIND:
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
