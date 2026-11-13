from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
from datetime import UTC, datetime

import pytest

from app.modules.devices.models import Device
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import WorkerTaskRead
from app.modules.users.models import User
from app.modules.workers.precheck_contract import PrecheckDeliveryAcknowledgement
from app.modules.workers.precheck_service import (PrecheckConflict, PrecheckNotFound,
    acknowledge_product_delivery, product_delivery_context, supports_saved_shop_sessions)


def fixture():
    task_id, device_id, user_id = uuid4(), uuid4(), uuid4()
    record = SimpleNamespace(client_id="product-library", product_id="12345678", revision=3)
    task = SimpleNamespace(task_id=task_id, target_device_id=device_id, skill_id="douyin.category_schema",
                           input_json={"_result_delivery": "product", "category_id": "123",
                                       "local_shop_id": "local", "platform_shop_id": "shop"},
                           status="running", result_json=None, error_code=None, error_message=None,
                           lease_until=None, finished_at=None)
    grant = SimpleNamespace(client_id="product-library", worker_precheck_enabled=True,
                            authorized_by_user_id=user_id, device_ids=(device_id,),
                            all_mapped_shops=(device_id,), device_shops=())
    objects = {Task: task, Device: SimpleNamespace(enabled=True, deleted_at=None),
               User: SimpleNamespace(enabled=True, is_super_account=True)}
    session = Mock()
    session.scalar.return_value = record
    session.get.side_effect = lambda model, key: objects[model]
    return session, Mock(current_grant=Mock(return_value=grant)), record, task, device_id


def test_only_compatible_worker_versions_receive_direct_tasks():
    assert not supports_saved_shop_sessions("0.5.1")
    assert supports_saved_shop_sessions("0.5.2")
    assert supports_saved_shop_sessions("0.6.0")
    assert not supports_saved_shop_sessions("unknown")


def test_legacy_claim_response_does_not_add_a_field_old_workers_reject():
    task = WorkerTaskRead(task_id=uuid4(), skill_id="system.echo", input={}, lease_until=datetime.now(UTC))
    assert "result_delivery" not in task.model_dump(mode="json", exclude_defaults=True)
    direct = task.model_copy(update={"result_delivery": "product"})
    assert direct.model_dump(mode="json", exclude_defaults=True)["result_delivery"] == "product"


def test_only_assigned_authorized_worker_can_read_delivery_context():
    session, auth, _, task, device_id = fixture()
    context = product_delivery_context(session, auth, device_id, task.task_id)
    assert context["product_id"] == "12345678" and context["revision"] == 3
    assert "result" not in context
    with pytest.raises(PrecheckNotFound):
        product_delivery_context(session, auth, uuid4(), task.task_id)
    auth.current_grant.return_value.worker_precheck_enabled = False
    with pytest.raises(PrecheckNotFound):
        product_delivery_context(session, auth, device_id, task.task_id)


def test_delivery_ack_stores_only_digest_and_is_idempotent():
    session, _, record, task, device_id = fixture()
    # The task is locked first so an already-acknowledged old task can be
    # replayed safely after its product revision is assigned to a new task.
    session.scalar.side_effect = [task, record, task, task]
    data = PrecheckDeliveryAcknowledgement(status="success", payload_sha256="a" * 64)
    assert acknowledge_product_delivery(session, device_id, task.task_id, data).result_json == {"delivery_sha256": "a" * 64}
    assert acknowledge_product_delivery(session, device_id, task.task_id, data).status == "success"
    with pytest.raises(PrecheckConflict):
        acknowledge_product_delivery(session, device_id, task.task_id,
                                     PrecheckDeliveryAcknowledgement(status="success", payload_sha256="b" * 64))
    session.commit.assert_called_once()
