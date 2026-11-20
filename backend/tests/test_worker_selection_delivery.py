from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.workers.precheck_contract import PrecheckDeliveryAcknowledgement
from app.modules.workers.selection_delivery import (
    SelectionDeliveryConflict, SelectionDeliveryNotFound, SelectionDeliveryUnavailable,
    acknowledge_delivery, delivery_context, mark_delivery_pending,
)


class Session:
    def __init__(self, task, device):
        self.task, self.device = task, device
        self.commits = 0

    def scalar(self, _statement):
        return self.task

    def get(self, _model, _identifier):
        return self.device

    def commit(self):
        self.commits += 1


@pytest.fixture
def context():
    device_id, task_id, correlation = uuid4(), uuid4(), uuid4()
    task = SimpleNamespace(task_id=task_id, target_device_id=device_id, skill_id='douyin.compass_selection',
        status='running', input_json={'correlation_id': str(correlation), 'operation': 'basic',
            '_worker_local_shops': [{'local_shop_id': 'shop-a', 'platform': 'douyin', 'platform_shop_id': '123'}]},
        result_json=None, error_code=None, error_message=None, lease_until=datetime.now(UTC), finished_at=None)
    return Session(task, SimpleNamespace(enabled=True, deleted_at=None)), device_id, task_id


def settings(origin='https://ops.example.test'):
    return Settings(_env_file=None, operations_selection_origin=origin)


def test_delivery_context_is_scoped_to_the_actual_worker_and_mapped_shop(context):
    session, device_id, task_id = context
    result = delivery_context(session, settings(), device_id, task_id)
    assert result['task_id'] == str(task_id) and result['device_id'] == str(device_id)
    assert result['platform_shop_id'] == '123' and result['operation'] == 'basic'
    with pytest.raises(SelectionDeliveryNotFound):
        delivery_context(session, settings(), uuid4(), task_id)
    session.task.input_json['_worker_local_shops'][0]['platform_shop_id'] = None
    with pytest.raises(SelectionDeliveryNotFound):
        delivery_context(session, settings(), device_id, task_id)


@pytest.mark.parametrize('origin', [None, 'http://ops.example.test', 'https://ops.example.test/?x=1',
                                   'https://user@ops.example.test', 'https://ops.example.test/../bad'])
def test_delivery_origin_must_be_a_configured_safe_https_location(context, origin):
    session, device_id, task_id = context
    with pytest.raises(SelectionDeliveryUnavailable):
        delivery_context(session, settings(origin), device_id, task_id)


def test_delivery_ack_is_idempotent_and_can_recover_lost_tasks(context):
    session, device_id, task_id = context
    session.task.status = 'lost'
    ack = PrecheckDeliveryAcknowledgement(status='success', payload_sha256='a' * 64)
    assert acknowledge_delivery(session, device_id, task_id, ack).status == 'success'
    assert session.task.result_json == {'delivery_sha256': 'a' * 64} and session.commits == 1
    acknowledge_delivery(session, device_id, task_id, ack)
    assert session.commits == 1
    with pytest.raises(SelectionDeliveryConflict):
        acknowledge_delivery(session, device_id, task_id,
                             PrecheckDeliveryAcknowledgement(status='success', payload_sha256='b' * 64))


def test_durable_pending_result_releases_task_and_only_the_same_receipt_can_finish(context):
    session, device_id, task_id = context
    ack = PrecheckDeliveryAcknowledgement(status='success', payload_sha256='a' * 64)
    pending = mark_delivery_pending(session, device_id, task_id, ack)
    assert pending.status == 'lost' and pending.error_code == 'SELECTION_DELIVERY_PENDING'
    assert pending.result_json['delivery_sha256'] == 'a' * 64 and session.commits == 1
    mark_delivery_pending(session, device_id, task_id, ack)
    assert session.commits == 1
    with pytest.raises(SelectionDeliveryConflict):
        acknowledge_delivery(session, device_id, task_id,
            PrecheckDeliveryAcknowledgement(status='success', payload_sha256='b' * 64))
    assert acknowledge_delivery(session, device_id, task_id, ack).status == 'success'
