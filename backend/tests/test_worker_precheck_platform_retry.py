import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import SecretStr, ValidationError

from app.core.security import redact_validation_errors
from app.modules.workers.precheck_contract import PrecheckSubmission
from app.modules.workers.precheck_models import ApplicationWorkerPrecheck
from app.modules.tasks.models import Task
from app.modules.workers.precheck_service import (PrecheckInvalidResult, PrecheckNotFound,
    PrecheckPlatformRetryExhausted, WorkerPrecheckService, _validate_platform_retry)


def task():
    return SimpleNamespace(target_device_id=uuid4(), input_json={
        "category_id": "123", "local_shop_id": "local", "platform_shop_id": "shop"})


def body(value, *, code=10004):
    return json.dumps({"status": "failed", "error_code": "PLATFORM_BUSINESS_REJECTED",
        "error_message": "预检未完成", "result": {"kind": "douyin.category_schema",
            "category_id": "123", "device_id": str(value.target_device_id), "local_shop_id": "local",
            "platform_shop_id": "shop", "http_status": 200, "platform_code": code,
            "error_stage": "platform", "safe_error_code": "PLATFORM_BUSINESS_REJECTED"}},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def test_proof_hashes_exact_utf8_and_rejects_unrelated_failures():
    value = task()
    original = body(value)
    assert _validate_platform_retry(value, SecretStr(original)) == hashlib.sha256(original.encode()).hexdigest()
    assert _validate_platform_retry(value, SecretStr(original + " ")) != hashlib.sha256(original.encode()).hexdigest()
    assert _validate_platform_retry(value, SecretStr(body(value, code="10004")))
    for text in (body(value, code=10008), original.replace('"error_stage":"platform"', '"error_stage":"session"'),
                 original.replace('"platform_shop_id":"shop"', '"platform_shop_id":"other"'),
                 original.replace('"status":"failed"', '"status":"success"'), "not json"):
        with pytest.raises(PrecheckInvalidResult):
            _validate_platform_retry(value, SecretStr(text))


def test_retry_validation_hides_contents_and_bounds_size():
    value = {"kind": "douyin.category_schema", "delivery": "product",
             "context": {"product_id": "one", "revision": 1, "attempt": 1},
             "input": {"category_id": "123", "title": "fixture"},
             "retry": {"previous_task_id": str(uuid4()), "terminal_json": "TEST_PRIVATE_" * 1000}}
    with pytest.raises(ValidationError) as caught:
        PrecheckSubmission.model_validate(value)
    errors = redact_validation_errors(caught.value.errors())
    assert "TEST_PRIVATE_" not in json.dumps(errors)
    value["retry"] = {"terminal_json": "TEST_PRIVATE_VALUE", "unexpected": True}
    with pytest.raises(ValidationError) as caught:
        PrecheckSubmission.model_validate(value)
    assert "TEST_PRIVATE_VALUE" not in json.dumps(redact_validation_errors(caught.value.errors()))


def test_v4_is_negotiated_without_changing_v3(monkeypatch):
    from fastapi import Response
    from app.modules.workers import precheck_api
    called = []
    monkeypatch.setattr(precheck_api, "product_delivery_context", lambda *args, **kwargs: called.append(kwargs) or {})
    principal = SimpleNamespace(device_id=uuid4())
    for protocol in ("2", "3", "4"):
        precheck_api.get_delivery_context(uuid4(), Response(), principal, object(), object(), protocol)
    assert called == [{"protocol_v2": True, "protocol_v3": False, "protocol_v4": False},
                      {"protocol_v2": True, "protocol_v3": True, "protocol_v4": False},
                      {"protocol_v2": True, "protocol_v3": True, "protocol_v4": True}]


def test_ack_race_and_old_retry_replay_never_dispatch_before_proof():
    previous = task()
    previous.task_id, previous.status = uuid4(), "running"
    previous.skill_id = "douyin.category_schema"
    previous.input_json.update({"_result_delivery": "product",
        "_precheck_context": {"client_id": "product", "product_id": "one", "revision": 1}})
    previous.result_json = None
    previous.error_code = None
    terminal = body(previous)
    request = PrecheckSubmission.model_validate({"kind": "douyin.category_schema", "delivery": "product",
        "context": {"product_id": "one", "revision": 1, "attempt": 1},
        "input": {"category_id": "123", "title": "fixture"},
        "retry": {"previous_task_id": str(previous.task_id), "terminal_json": terminal}})
    request_data = {"kind": request.kind, "input": request.input.model_dump(mode="json", exclude_defaults=True),
                    "delivery": "product"}
    digest = hashlib.sha256(json.dumps(request_data, sort_keys=True, ensure_ascii=False,
                                       separators=(",", ":")).encode()).hexdigest()
    record = SimpleNamespace(request_hash=digest, task_id=previous.task_id)
    current = SimpleNamespace(task_id=uuid4(), target_device_id=previous.target_device_id,
                              input_json={"local_shop_id": "local2", "platform_shop_id": "shop2"})
    session = Mock()
    def lookup(model, identity):
        if model is ApplicationWorkerPrecheck:
            return record
        if model is Task:
            return previous if identity == previous.task_id else current
        raise AssertionError("unexpected database model")
    session.get.side_effect = lookup
    grant = SimpleNamespace(client_id="product", precheck_context=None,
                            all_precheck_devices=True, excluded_precheck_devices=())
    service = WorkerPrecheckService(session, Mock())
    service._grant = lambda principal: grant
    assert service.submit(object(), request) is previous
    session.add.assert_not_called()
    previous.status = "failed"
    previous.error_code = "PLATFORM_BUSINESS_REJECTED"
    previous.result_json = {"delivery_sha256": hashlib.sha256(terminal.encode()).hexdigest()}
    record.task_id = current.task_id
    assert service.submit(object(), request) is current
    forged = request.model_copy(update={"retry": request.retry.model_copy(
        update={"terminal_json": SecretStr(terminal + " ")})})
    with pytest.raises(PrecheckInvalidResult):
        service.submit(object(), forged)
    previous.input_json["_precheck_context"]["product_id"] = "different-product"
    with pytest.raises(PrecheckNotFound):
        service.submit(object(), request)
    session.add.assert_not_called()


def test_exhausted_is_a_distinct_http_409():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.config import Settings, get_settings
    from app.modules.workers.precheck_api import _service, require_precheck_application

    class Service:
        def submit(self, principal, data):
            raise PrecheckPlatformRetryExhausted()

    app.dependency_overrides[get_settings] = lambda: Settings(application_worker_precheck_enabled=True)
    app.dependency_overrides[require_precheck_application] = lambda: object()
    app.dependency_overrides[_service] = lambda: Service()
    try:
        with TestClient(app) as client:
            payload = {
                "kind": "douyin.category_schema", "delivery": "product",
                "context": {"product_id": "one", "revision": 1, "attempt": 1},
                "input": {"category_id": "123", "title": "fixture"}}
            result = client.post("/internal/applications/v1/worker-prechecks", json=payload)
            assert result.status_code == 409
            assert result.json()["code"] == "PRECHECK_PLATFORM_RETRY_EXHAUSTED"
            payload["retry"] = {"previous_task_id": str(uuid4()), "terminal_json": "TEST_PRIVATE_" * 1000}
            rejected = client.post("/internal/applications/v1/worker-prechecks", json=payload)
            assert rejected.status_code == 422 and "TEST_PRIVATE_" not in rejected.text
    finally:
        app.dependency_overrides.clear()
