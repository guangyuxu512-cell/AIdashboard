"""Task-bound result routing for the independently hosted operations center."""
from datetime import UTC, datetime
import re
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError
from app.modules.devices.models import Device
from app.modules.tasks.models import Task
from app.modules.workers.precheck_contract import PrecheckDeliveryAcknowledgement
from app.modules.workers.shop_context import LOCAL_SHOPS_KEY


SELECTION_SKILL = 'douyin.compass_selection'
MERCHANT_SKILL = 'douyin.merchant_products'


class SelectionDeliveryUnavailable(AppError):
    code = 'SELECTION_DELIVERY_UNAVAILABLE'
    message = '运营中心结果接收服务不可用'
    status_code = 503


class SelectionDeliveryNotFound(AppError):
    code = 'SELECTION_DELIVERY_NOT_FOUND'
    message = '选品任务不存在或无权访问'
    status_code = 404


class SelectionDeliveryConflict(AppError):
    code = 'SELECTION_DELIVERY_CONFLICT'
    message = '选品任务回执与已有结果不一致'
    status_code = 409


def _destination(settings: Settings) -> str:
    value = settings.operations_selection_origin
    try:
        parsed = urlsplit(value or '')
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.port not in (None, 443)
                or re.fullmatch(r'(?:/[A-Za-z0-9_-]+)*/?', parsed.path) is None
                or any(ord(char) < 33 or ord(char) == 127 for char in (value or ''))
                or len(value or '') > 2048):
            raise ValueError('invalid destination')
    except ValueError:
        raise SelectionDeliveryUnavailable() from None
    return (value or '').rstrip('/')


def _owned_task(session: Session, device_id: UUID, task_id: UUID, *, lock: bool = False) -> Task:
    statement = select(Task).where(Task.task_id == task_id)
    if lock:
        statement = statement.with_for_update()
    task = session.scalar(statement)
    device = session.get(Device, device_id)
    shops = task.input_json.get(LOCAL_SHOPS_KEY, []) if task and isinstance(task.input_json, dict) else []
    if (task is None or task.target_device_id != device_id or task.skill_id not in {SELECTION_SKILL, MERCHANT_SKILL}
            or task.status not in ('running', 'lost', 'success', 'failed')
            or device is None or not device.enabled or device.deleted_at is not None
            or not isinstance(shops, list) or len(shops) != 1 or not isinstance(shops[0], dict)
            or shops[0].get('platform') != 'douyin' or not shops[0].get('platform_shop_id')):
        raise SelectionDeliveryNotFound()
    try:
        UUID(task.input_json['correlation_id'])
        allowed = ('categories', 'rank', 'basic') if task.skill_id == SELECTION_SKILL else ('list',)
        if task.input_json['operation'] not in allowed:
            raise ValueError('invalid operation')
    except (KeyError, TypeError, ValueError):
        raise SelectionDeliveryNotFound() from None
    return task


def delivery_context(session: Session, settings: Settings, device_id: UUID, task_id: UUID) -> dict:
    task = _owned_task(session, device_id, task_id)
    shop = task.input_json[LOCAL_SHOPS_KEY][0]
    return {'task_id': str(task_id), 'device_id': str(device_id), 'skill_id': task.skill_id, 'origin': _destination(settings),
            'correlation_id': task.input_json['correlation_id'], 'operation': task.input_json['operation'],
            'local_shop_id': shop['local_shop_id'], 'platform_shop_id': shop['platform_shop_id']}


def acknowledge_delivery(session: Session, device_id: UUID, task_id: UUID,
                         data: PrecheckDeliveryAcknowledgement) -> Task:
    task = _owned_task(session, device_id, task_id, lock=True)
    receipt = {'delivery_sha256': data.payload_sha256}
    if task.status in ('success', 'failed'):
        if task.status == data.status and task.result_json == receipt and task.error_code == data.error_code:
            return task
        raise SelectionDeliveryConflict()
    if isinstance(task.result_json, dict) and task.result_json.get('delivery_pending') is True:
        if (task.result_json.get('delivery_sha256') != data.payload_sha256
                or task.result_json.get('terminal_status') != data.status
                or task.result_json.get('terminal_error_code') != data.error_code):
            raise SelectionDeliveryConflict()
    task.status = data.status
    task.result_json = receipt
    task.error_code = data.error_code
    task.error_message = '设备选品未完成' if data.status == 'failed' else None
    task.lease_until = None
    task.finished_at = datetime.now(UTC)
    session.commit()
    return task


def mark_delivery_pending(session: Session, device_id: UUID, task_id: UUID,
                          data: PrecheckDeliveryAcknowledgement) -> Task:
    """Release the execution slot only after the Worker has durably stored the result."""
    task = _owned_task(session, device_id, task_id, lock=True)
    pending = {'delivery_pending': True, 'delivery_sha256': data.payload_sha256,
               'terminal_status': data.status, 'terminal_error_code': data.error_code}
    if task.status in ('success', 'failed'):
        if (task.status == data.status and task.result_json == {'delivery_sha256': data.payload_sha256}
                and task.error_code == data.error_code):
            return task
        raise SelectionDeliveryConflict()
    if task.result_json not in (None, pending):
        raise SelectionDeliveryConflict()
    if task.status == 'lost' and task.result_json == pending:
        return task
    task.status = 'lost'
    task.result_json = pending
    task.error_code = 'SELECTION_DELIVERY_PENDING'
    task.error_message = '选品结果等待回传'
    task.lease_until = None
    task.finished_at = None
    session.commit()
    return task
