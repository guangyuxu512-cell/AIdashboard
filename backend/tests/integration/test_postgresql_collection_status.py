"""Isolated authoritative NAS failure reconciliation; no NAS/device/platform I/O."""
from dataclasses import replace
from datetime import timedelta
import json
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from app.core.config import get_settings
from app.modules.product_collection.contracts import GatewayAttemptRegistrationV1
from app.modules.product_collection.dispatch_service import ProductCollectionDispatchService
from app.modules.product_collection.executor import ProductCollectionExecutor
from app.modules.product_collection.ingest_service import ProductCollectionIngestService
from app.modules.product_collection.gateway import HttpProductCollectionGateway
from app.modules.product_collection.models import (
    ProductCollectionCaptureAttempt as Attempt, ProductCollectionDispatch as Dispatch,
    ProductCollectionItem as Item, ProductCollectionRequest as CollectionRequest,
    ProductCollectionUploadReceipt as Upload,
)
from tests.integration.test_postgresql_collection_media_budget import (
    isolated_collection, _settings, _submit, _gateway as delivery_gateway,
)
from tests.test_product_collection_status import status_body
from tests.test_product_collection_media_urls import _body, COMMENTS, IMAGE_URL


pytestmark = pytest.mark.integration
SECRET = b"synthetic-status-secret-at-least-32-bytes"


def register(sessions, item_id, number):
    with sessions() as session:
        item = session.get(Item, item_id)
        dispatch = session.get(Dispatch, item.current_dispatch_id)
        registration = GatewayAttemptRegistrationV1(
            schemaVersion=1, dispatchId=dispatch.dispatch_id, gatewayId=dispatch.gateway_id,
            externalJobId=dispatch.external_job_id, gatewayJobId=dispatch.gateway_job_id,
            deviceId="synthetic-status-device", captureBatchId=f"synthetic-status-batch-{number}",
            sourcePlatform="douyin", sourceProductId=item.source_product_id,
            leaseExpiresAt=session.scalar(select(func.clock_timestamp())) + timedelta(minutes=15),
        )
        return ProductCollectionIngestService(session).register_attempt(
            registration, secret=SECRET, key_id="synthetic-key", public_base_url="https://central.example.test",
            token_ttl_seconds=600, accept_grace_seconds=600,
        )


def running(isolated_collection, attempts=3):
    app, client, sessions = isolated_collection
    settings = _settings(3).model_copy(update={
        "product_collection_gateway_id": "synthetic-gateway",
        "product_collection_service_token": SecretStr("synthetic-service-token"),
        "product_collection_ingest_hmac_key": SecretStr(SECRET.decode()),
    })
    app.dependency_overrides[get_settings] = lambda: settings
    request_id = _submit(client)
    gateway, _ = delivery_gateway()
    with sessions() as session:
        service = ProductCollectionDispatchService(session)
        assert service.plan_pending(gateway_id="synthetic-gateway") == 1
        assert service.deliver_once(gateway, lease_seconds=60, max_attempts=3, retry_delay_seconds=1)
        item = session.scalar(select(Item).where(Item.request_id == request_id))
        item_id, dispatch_id = item.item_id, item.current_dispatch_id
    controls = [register(sessions, item_id, n) for n in range(1, attempts + 1)]
    with sessions() as session:
        dispatch = session.get(Dispatch, dispatch_id)
        response = status_body(
            jobId=dispatch.gateway_job_id, externalJobId=dispatch.external_job_id,
            captureBatchId=f"synthetic-status-batch-{attempts}", attempts=attempts,
        )
    return app, client, sessions, settings, request_id, item_id, dispatch_id, controls, response


def status_gateway(response, handler=None):
    return HttpProductCollectionGateway(base_url="https://gateway.example.test", gateway_id="synthetic-gateway",
        control_token=SecretStr("synthetic-control-token"), callback_token=None, timeout_seconds=2,
        client=httpx.Client(transport=httpx.MockTransport(handler or (lambda _: httpx.Response(200, json=response)))))


def claim(sessions):
    with sessions() as session:
        result = ProductCollectionDispatchService(session).repository.claim_gateway_status(
            gateway_id="synthetic-gateway", interval_seconds=30,
        )
        session.commit()
        return result


def test_failed_three_attempts_converge_and_existing_human_api_reports_safe_error(isolated_collection):
    _, client, sessions, settings, request_id, item_id, dispatch_id, controls, response = running(isolated_collection)
    reads = []

    def handle(request):
        reads.append(request.method)
        return httpx.Response(200, json=response)

    executor = ProductCollectionExecutor(session_factory=sessions, settings=settings,
        gateway=status_gateway(response, handle), cleaner=None)
    assert executor.dispatch_once()
    snapshot = client.get(f"/api/v1/product-collection/requests/{request_id}").json()
    assert snapshot["status"] == "failed" and snapshot["items"][0]["state"] == "failed"
    assert snapshot["items"][0]["last_error_code"] == "PRODUCT_COLLECTION_GATEWAY_EXECUTION_FAILED"
    assert snapshot["items"][0]["last_error_stage"] == "gateway_execution"
    assert snapshot["items"][0]["last_error_message"] == "手机采集等待本批次完整包超时（尝试 3/3 次）"
    with sessions() as session:
        dispatch = session.get(Dispatch, dispatch_id)
        attempts = list(session.scalars(select(Attempt).where(Attempt.dispatch_id == dispatch_id).order_by(Attempt.attempt_no)))
        assert dispatch.state == "execution_failed" and dispatch.next_attempt_at is None
        assert [a.state for a in attempts] == ["superseded", "superseded", "failed"]
        assert attempts[-1].last_error_message == dispatch.last_error_message
        assert session.scalar(select(func.count()).select_from(Upload)) == 0
        assert session.get(Item, item_id).attempt_count == 3
    assert not executor.dispatch_once() and reads == ["GET"]
    assert client.get(f"/api/v1/product-collection/requests/{request_id}").json() == snapshot
    assert client.post(f"/api/v1/product-collection/items/{item_id}/retry").status_code == 409
    assert client.post(f"/api/v1/product-collection/items/{item_id}/recapture").status_code == 200
    with sessions() as session:
        assert session.get(Item, item_id).current_dispatch_id != dispatch_id
        assert session.get(Dispatch, dispatch_id).state == "execution_failed"


@pytest.mark.parametrize("state", ["pending", "running", "retry_wait", "captured", "completed", "canceled", "unknown"])
def test_non_failed_and_unknown_status_preserve_business_state_and_cooldown(isolated_collection, state):
    _, client, sessions, settings, request_id, _, _, _, response = running(isolated_collection)
    before = client.get(f"/api/v1/product-collection/requests/{request_id}").json()
    gateway = status_gateway({**response, "status": state})
    with sessions() as session:
        service = ProductCollectionDispatchService(session)
        assert not service.reconcile_gateway_once(gateway, gateway_id="synthetic-gateway", interval_seconds=30)
        assert not session.in_transaction()
        assert not service.reconcile_gateway_once(gateway, gateway_id="synthetic-gateway", interval_seconds=30)
    assert client.get(f"/api/v1/product-collection/requests/{request_id}").json() == before


def test_network_error_preserves_state_and_does_not_hold_transaction(isolated_collection):
    _, client, sessions, _, request_id, _, _, _, response = running(isolated_collection)
    before = client.get(f"/api/v1/product-collection/requests/{request_id}").json()
    with sessions() as session:
        def fail(request):
            assert not session.in_transaction()
            raise httpx.ReadTimeout("synthetic-private-error", request=request)
        service = ProductCollectionDispatchService(session)
        assert not service.reconcile_gateway_once(status_gateway(response, fail),
            gateway_id="synthetic-gateway", interval_seconds=30)
    assert client.get(f"/api/v1/product-collection/requests/{request_id}").json() == before


@pytest.mark.parametrize("field,value", [
    ("gateway_id", "other-gateway"), ("gateway_job_id", "other-job"),
    ("external_job_id", "other-external"), ("source_product_id", "other-product"),
    ("capture_batch_id", "old-batch"), ("source_platform", "pinduoduo"),
])
def test_mismatched_status_identity_cannot_end_current_attempt(isolated_collection, field, value):
    _, client, sessions, _, request_id, _, _, _, response = running(isolated_collection)
    before = client.get(f"/api/v1/product-collection/requests/{request_id}").json()
    captured = claim(sessions)
    result = status_gateway(response).status(gateway_job_id=response["jobId"], external_job_id=response["externalJobId"])
    with sessions() as session:
        assert not ProductCollectionDispatchService(session).reconcile_gateway_failure(captured, replace(result, **{field: value}))
    assert client.get(f"/api/v1/product-collection/requests/{request_id}").json() == before


def test_old_attempt_and_old_dispatch_results_do_not_affect_new_work(isolated_collection):
    _, client, sessions, _, request_id, item_id, dispatch_id, _, response = running(isolated_collection, attempts=2)
    captured = claim(sessions)
    old_result = status_gateway(response).status(gateway_job_id=response["jobId"], external_job_id=response["externalJobId"])
    register(sessions, item_id, 3)
    with sessions() as session:
        assert not ProductCollectionDispatchService(session).reconcile_gateway_failure(captured, old_result)
        assert session.get(Dispatch, dispatch_id).state == "running"
        session.get(Dispatch, dispatch_id).next_attempt_at = None
        session.commit()
    current_claim = claim(sessions)
    current_result = replace(old_result, capture_batch_id="synthetic-status-batch-3", attempts=3)
    with sessions() as session:
        assert ProductCollectionDispatchService(session).reconcile_gateway_failure(current_claim, current_result)
        assert not ProductCollectionDispatchService(session).reconcile_gateway_failure(current_claim, current_result)
    assert client.post(f"/api/v1/product-collection/items/{item_id}/recapture").status_code == 200
    with sessions() as session:
        new_id = session.get(Item, item_id).current_dispatch_id
        assert not ProductCollectionDispatchService(session).reconcile_gateway_failure(current_claim, current_result)
        assert session.get(Dispatch, new_id).state == "pending_delivery"
        assert session.get(Item, item_id).current_dispatch_id == new_id


@pytest.mark.parametrize("field", ["team_id", "attempt_id", "gateway_device_id"])
def test_frozen_claim_identity_is_rechecked(isolated_collection, field):
    _, client, sessions, _, request_id, _, _, _, response = running(isolated_collection)
    before = client.get(f"/api/v1/product-collection/requests/{request_id}").json()
    captured = claim(sessions)
    wrong = replace(captured, **{field: "another-device" if field == "gateway_device_id" else uuid4()})
    result = status_gateway(response).status(gateway_job_id=response["jobId"], external_job_id=response["externalJobId"])
    with sessions() as session:
        assert not ProductCollectionDispatchService(session).reconcile_gateway_failure(wrong, result)
    assert client.get(f"/api/v1/product-collection/requests/{request_id}").json() == before


def test_accepted_upload_during_status_http_is_not_overwritten(isolated_collection):
    _, client, sessions, _, request_id, item_id, dispatch_id, controls, response = running(isolated_collection)
    current = controls[-1]
    raw = _body(f"{COMMENTS}.comment_medias_arr.*.media_image_src", IMAGE_URL)
    raw["taskContext"]["jobId"] = response["jobId"]
    raw["taskContext"]["captureBatchId"] = response["captureBatchId"]
    with sessions() as session:
        def handle(_):
            assert not session.in_transaction()
            received = client.post(f"/api/v1/mobile-collection/ingest/{current.attempt_id}",
                content=json.dumps(raw).encode(), headers={"Authorization": f"Bearer {current.credential}",
                    "Content-Type": "application/json"})
            assert received.status_code == 202
            return httpx.Response(200, json=response)
        service = ProductCollectionDispatchService(session)
        assert not service.reconcile_gateway_once(status_gateway(response, handle),
            gateway_id="synthetic-gateway", interval_seconds=30)
        assert session.get(Item, item_id).state == "received"
        assert session.get(Attempt, current.attempt_id).state == "received"
        assert session.get(Dispatch, dispatch_id).state == "running"
        assert session.scalar(select(func.count()).select_from(Upload)) == 1
        assert service.repository.claim_gateway_status(gateway_id="synthetic-gateway", interval_seconds=30) is None
    read = client.get(f"/api/v1/product-collection/requests/{request_id}").json()
    assert read["running_count"] == 1 and read["items"][0]["state"] == "received"
