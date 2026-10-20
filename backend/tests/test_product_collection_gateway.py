from datetime import UTC, datetime
import json
from uuid import uuid4

import httpx
from pydantic import SecretStr
import pytest

from app.modules.product_collection.contracts import GatewaySettlementV1, SourcePlatform
from app.modules.product_collection.gateway import (
    HttpProductCollectionGateway,
    ProductCollectionGatewayError,
)
from app.modules.product_collection.ports import GatewayDispatchCommand


CONTROL_TOKEN = "synthetic-control-token"
CALLBACK_TOKEN = "synthetic-callback-token"
GATEWAY_ID = "gateway-a"


def _command() -> GatewayDispatchCommand:
    return GatewayDispatchCommand(
        dispatch_id=uuid4(),
        external_job_id="pcd_v1_test",
        canonical_payload_hash="a" * 64,
        source_platform=SourcePlatform.DOUYIN,
        source_product_id="3832497447662387684",
    )


def _gateway(handler) -> HttpProductCollectionGateway:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return HttpProductCollectionGateway(
        base_url="https://gateway.example.test",
        gateway_id=GATEWAY_ID,
        control_token=SecretStr(CONTROL_TOKEN),
        callback_token=SecretStr(CALLBACK_TOKEN),
        timeout_seconds=5,
        client=client,
    )


def test_dispatch_uses_exact_service_contract_and_validates_identity() -> None:
    command = _command()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/jobs"
        assert request.headers["authorization"] == f"Bearer {CONTROL_TOKEN}"
        assert request.headers["content-type"].startswith("application/json")
        body = json.loads(request.content)
        assert body == command.payload()
        return httpx.Response(
            201,
            request=request,
            json={
                "ok": True,
                "gatewayId": GATEWAY_ID,
                "requested": 1,
                "accepted": [{"jobId": "gateway-job-a"}],
                "acceptedCount": 1,
                "reused": [],
                "reusedCount": 0,
                "skipped": [],
                "skippedCount": 0,
                "invalid": [],
                "dispatch": {
                    "dispatchId": str(command.dispatch_id),
                    "gatewayId": GATEWAY_ID,
                    "gatewayJobId": "gateway-job-a",
                    "externalJobId": command.external_job_id,
                    "canonicalPayloadHash": command.canonical_payload_hash,
                    "sourcePlatform": "douyin",
                    "sourceProductId": command.source_product_id,
                    "ingestMode": "central_ingest_v1",
                    "jobType": "product",
                    "status": "pending",
                    "reused": False,
                },
            },
        )

    result = _gateway(handler).deliver(command)
    assert result.gateway_job_id == "gateway-job-a"
    assert result.status == "pending" and not result.reused


def test_dispatch_rejects_mismatched_or_secret_bearing_errors() -> None:
    command = _command()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            request=request,
            json={
                "ok": True,
                "gatewayId": GATEWAY_ID,
                "requested": 1,
                "accepted": [],
                "acceptedCount": 0,
                "reused": [{}],
                "reusedCount": 1,
                "skipped": [],
                "skippedCount": 0,
                "invalid": [],
                "dispatch": {
                    "dispatchId": str(command.dispatch_id),
                    "gatewayId": GATEWAY_ID,
                    "gatewayJobId": "gateway-job-a",
                    "externalJobId": command.external_job_id,
                    "canonicalPayloadHash": "b" * 64,
                    "sourcePlatform": "douyin",
                    "sourceProductId": command.source_product_id,
                    "ingestMode": "central_ingest_v1",
                    "jobType": "product",
                    "status": "pending",
                    "reused": True,
                },
            },
        )

    with pytest.raises(ProductCollectionGatewayError) as captured:
        _gateway(handler).deliver(command)
    assert captured.value.failure_code == "PRODUCT_COLLECTION_GATEWAY_RESPONSE_INVALID"
    assert CONTROL_TOKEN not in str(captured.value)


def test_retry_and_cancel_use_existing_gateway_job() -> None:
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.url.path == "/api/v1/jobs/retry":
            return httpx.Response(
                200,
                request=request,
                json={
                    "ok": True,
                    "reset": ["gateway-job-a"],
                    "items": [
                        {
                            "gatewayJobId": "gateway-job-a",
                            "externalJobId": "pcd_v1_original",
                            "status": "pending",
                            "attempts": 2,
                            "maxAttempts": 3,
                        },
                    ],
                },
            )
        assert request.url.path == "/api/v1/jobs/gateway-job-a"
        return httpx.Response(
            200,
            request=request,
            json={
                "ok": True,
                "job": {
                    "jobId": "gateway-job-a",
                    "externalJobId": "pcd_v1_original",
                    "status": "canceled",
                    "captureBatchId": "batch-a",
                    "deviceId": "device-a",
                    "lastError": "CONTROL_CANCELED",
                    "unrelatedNormalizeJobField": "allowed",
                },
            },
        )

    gateway = _gateway(handler)
    result = gateway.retry(gateway_job_id="gateway-job-a")
    gateway.cancel(gateway_job_id="gateway-job-a")
    assert result.gateway_job_id == "gateway-job-a"
    assert result.external_job_id == "pcd_v1_original"
    assert requests == [
        ("POST", "/api/v1/jobs/retry"),
        ("PATCH", "/api/v1/jobs/gateway-job-a"),
    ]


def test_settlement_uses_callback_token_and_alias_payload() -> None:
    settlement = GatewaySettlementV1.model_validate(
        {
            "schemaVersion": 1,
            "dispatchId": uuid4(),
            "gatewayId": GATEWAY_ID,
            "externalJobId": "pcd_v1_original",
            "gatewayJobId": "gateway-job-a",
            "captureBatchId": "batch-a",
            "deviceId": "device-a",
            "sourcePlatform": "douyin",
            "sourceProductId": "3832497447662387684",
            "attemptId": uuid4(),
            "receiptId": uuid4(),
            "status": "succeeded",
            "productVersionId": uuid4(),
            "uuSha256": "c" * 64,
            "persistedAt": datetime.now(UTC),
        },
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/control/collection-settlements"
        assert request.headers["authorization"] == f"Bearer {CALLBACK_TOKEN}"
        body = json.loads(request.content)
        assert body["gatewayJobId"] == "gateway-job-a"
        assert body["productVersionId"] == str(settlement.product_version_id)
        assert "job_id" not in body
        return httpx.Response(
            200,
            request=request,
            json={
                "ok": True,
                "settlement": {
                    "status": "applied",
                    "gatewayJobId": "gateway-job-a",
                    "captureBatchId": "batch-a",
                    "jobStatus": "completed",
                },
            },
        )

    _gateway(handler).settle(settlement)


@pytest.mark.parametrize(
    ("status_code", "retryable", "failure_code"),
    [
        (401, False, "PRODUCT_COLLECTION_GATEWAY_AUTHENTICATION_FAILED"),
        (409, False, "PRODUCT_COLLECTION_GATEWAY_STATE_CONFLICT"),
        (429, True, "PRODUCT_COLLECTION_GATEWAY_RATE_LIMITED"),
        (503, True, "PRODUCT_COLLECTION_GATEWAY_UNAVAILABLE"),
    ],
)
def test_gateway_http_failures_are_safe_and_classified(
    status_code: int,
    retryable: bool,
    failure_code: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            request=request,
            json={"secret": CONTROL_TOKEN},
        )

    with pytest.raises(ProductCollectionGatewayError) as captured:
        _gateway(handler).deliver(_command())
    assert captured.value.retryable is retryable
    assert captured.value.failure_code == failure_code
    assert CONTROL_TOKEN not in str(captured.value)


def test_invalid_gateway_base_url_and_empty_tokens_fail_closed() -> None:
    with pytest.raises(ValueError):
        HttpProductCollectionGateway(
            base_url="https://user:password@gateway.example.test?token=secret",
            gateway_id=GATEWAY_ID,
            control_token=SecretStr(CONTROL_TOKEN),
            callback_token=SecretStr(CALLBACK_TOKEN),
            timeout_seconds=5,
        )


def test_settlement_conflict_is_terminal_and_safely_classified() -> None:
    settlement = GatewaySettlementV1.model_validate(
        {
            "schemaVersion": 1,
            "dispatchId": uuid4(),
            "gatewayId": GATEWAY_ID,
            "externalJobId": "pcd_v1_original",
            "gatewayJobId": "gateway-job-a",
            "captureBatchId": "batch-a",
            "deviceId": "device-a",
            "sourcePlatform": "douyin",
            "sourceProductId": "3832497447662387684",
            "attemptId": uuid4(),
            "receiptId": uuid4(),
            "status": "failed",
            "errorCode": "PRODUCT_COLLECTION_CLEANER_INVALID",
            "errorMessage": "商品完整包清洗失败",
            "persistedAt": datetime.now(UTC),
        },
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, request=request, json={"ignored": "sensitive"})

    with pytest.raises(ProductCollectionGatewayError) as captured:
        _gateway(handler).settle(settlement)
    assert captured.value.failure_code == "PRODUCT_COLLECTION_GATEWAY_SETTLEMENT_REJECTED"
    assert captured.value.retryable is False
    with pytest.raises(ValueError):
        HttpProductCollectionGateway(
            base_url="https://gateway.example.test",
            gateway_id=GATEWAY_ID,
            control_token=SecretStr(""),
            callback_token=SecretStr(CALLBACK_TOKEN),
            timeout_seconds=5,
        )
