from datetime import UTC, datetime, timedelta
import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.product_collection.contracts import (
    GatewayAttemptRegistrationV1,
    GatewaySettlementV1,
    ProductCollectionRequestCreate,
)
from app.modules.product_collection.exceptions import ProductCollectionTargetUnsupportedError
from app.modules.product_collection.payload import (
    MAX_COMPLETE_PACKAGE_BYTES,
    parse_complete_package,
    sanitize_image_url,
    sanitize_source_url,
)
from app.modules.product_collection.security import (
    CredentialBinding,
    issue_credential,
    verify_credential_hash,
)
from app.modules.product_collection.state_machine import (
    ATTEMPT_ACTIVE,
    DISPATCH_ACTIVE,
    AttemptState,
    DispatchState,
    ItemState,
    SettlementState,
    can_transition,
)
from app.modules.product_collection.targets import distinct_targets, normalize_manual_target


def test_request_hash_is_stable_and_rejects_unknown_fields():
    submission_key = uuid4()
    body = {
        "submission_key": submission_key,
        "target_group_id": None,
        "source": {
            "kind": "manual",
            "targets": [
                {"platform": "douyin", "product_id_or_supported_url": "3832497447662387684"},
            ],
        },
    }
    first = ProductCollectionRequestCreate.model_validate(body)
    second = ProductCollectionRequestCreate.model_validate(body)
    assert first.canonical_hash() == second.canonical_hash()
    with pytest.raises(ValidationError):
        ProductCollectionRequestCreate.model_validate({**body, "team_id": str(uuid4())})


def test_attempt_registration_is_douyin_only_and_requires_timezone():
    body = {
        "schemaVersion": 1,
        "dispatchId": uuid4(),
        "gatewayId": "gateway-a",
        "externalJobId": "dispatch-a",
        "gatewayJobId": "job-a",
        "deviceId": "device-a",
        "captureBatchId": "batch-a",
        "sourcePlatform": "douyin",
        "sourceProductId": "3832497447662387684",
        "leaseExpiresAt": datetime.now(UTC) + timedelta(minutes=15),
    }
    assert GatewayAttemptRegistrationV1.model_validate(body).source_platform == "douyin"
    with pytest.raises(ValidationError):
        GatewayAttemptRegistrationV1.model_validate({**body, "sourcePlatform": "pinduoduo"})
    with pytest.raises(ValidationError):
        GatewayAttemptRegistrationV1.model_validate(
            {**body, "leaseExpiresAt": datetime.now().replace(tzinfo=None)},
        )


def test_complete_package_has_strict_allowlist_and_rejects_credentials():
    body = {
        "eventType": "complete",
        "detailBody": {"data": {"product_id": "3832497447662387684"}},
        "skuBody": {"data": {"product_id": "3832497447662387684"}},
        "capturedAt": 1792470000000,
        "skuCapturedAt": 1792470001000,
        "taskContext": {
            "jobId": "job-a",
            "captureBatchId": "batch-a",
            "jobType": "product-detail-v1",
            "sourcePlatform": "douyin",
            "sourceProductId": "3832497447662387684",
        },
    }
    parsed = parse_complete_package(json.dumps(body).encode())
    assert parsed.task_context.source_product_id == "3832497447662387684"
    with pytest.raises(ValueError, match="credential"):
        parse_complete_package(
            json.dumps({**body, "detailBody": {"cookie": "forbidden"}}).encode(),
        )
    with pytest.raises(ValueError, match="credential"):
        parse_complete_package(
            json.dumps(
                {
                    **body,
                    "detailBody": {
                        "image": "https://img.example.test/a.webp?a_bogus=secret",
                    },
                },
            ).encode(),
        )
    with pytest.raises(ValueError, match="credential"):
        parse_complete_package(
            json.dumps(
                {
                    **body,
                    "detailBody": {
                        "image": "  HTTPS://img.example.test/a.webp?Access-Token=secret",
                    },
                },
            ).encode(),
        )
    safe_url = parse_complete_package(
        json.dumps(
            {
                **body,
                "detailBody": {
                    "image": "https://img.example.test/a.webp?width=64",
                },
            },
        ).encode(),
    )
    assert safe_url.detail_body["image"].endswith("?width=64")
    with pytest.raises(ValueError, match="oversized URL"):
        parse_complete_package(
            json.dumps(
                {
                    **body,
                    "detailBody": {
                        "image": "https://img.example.test/" + "a" * 4097,
                    },
                },
            ).encode(),
        )
    with pytest.raises(ValidationError):
        parse_complete_package(json.dumps({**body, "headers": {}}).encode())
    with pytest.raises(ValueError, match="size"):
        parse_complete_package(b"{" + b" " * MAX_COMPLETE_PACKAGE_BYTES + b"}")
    with pytest.raises(ValueError, match="non-finite"):
        parse_complete_package(
            json.dumps({**body, "detailBody": {"price": float("nan")}}).encode(),
        )


def test_source_and_image_url_sanitization_remove_secret_context():
    assert sanitize_source_url(
        "https://example.test/product/123?token=secret#fragment",
    ) == "https://example.test/product/123"
    assert sanitize_image_url(
        "https://img.example.test/a.jpg?width=64&token=secret#x",
        allowed_hosts=frozenset({"img.example.test"}),
        safe_query_keys=frozenset({"width"}),
    ) == "https://img.example.test/a.jpg?width=64"
    with pytest.raises(ValueError, match="userinfo"):
        sanitize_source_url("https://user:secret@example.test/a")


def test_ingest_credential_is_idempotently_derived_and_batch_bound():
    binding = CredentialBinding(
        attempt_id=uuid4(),
        gateway_id="gateway-a",
        device_id="device-a",
        gateway_job_id="job-a",
        capture_batch_id="batch-a",
        source_platform="douyin",
        source_product_id="3832497447662387684",
    )
    secret = b"a" * 32
    credential_id = uuid4()
    salt = b"b" * 16
    first = issue_credential(
        secret=secret,
        binding=binding,
        version=1,
        credential_id=credential_id,
        salt=salt,
    )
    replay = issue_credential(
        secret=secret,
        binding=binding,
        version=1,
        credential_id=credential_id,
        salt=salt,
    )
    assert first == replay
    assert verify_credential_hash(first.token, first.token_sha256)
    other_batch = CredentialBinding(**{**binding.__dict__, "capture_batch_id": "batch-b"})
    changed = issue_credential(
        secret=secret,
        binding=other_batch,
        version=1,
        credential_id=credential_id,
        salt=salt,
    )
    assert changed.token != first.token
    assert not verify_credential_hash(changed.token, first.token_sha256)


def test_settlement_never_treats_received_only_as_success():
    base = {
        "dispatchId": uuid4(),
        "gatewayId": "gateway-a",
        "externalJobId": "dispatch-a",
        "gatewayJobId": "job-a",
        "captureBatchId": "batch-a",
        "deviceId": "device-a",
        "sourcePlatform": "douyin",
        "sourceProductId": "3832497447662387684",
        "attemptId": uuid4(),
        "receiptId": uuid4(),
        "persistedAt": datetime.now(UTC),
    }
    with pytest.raises(ValidationError):
        GatewaySettlementV1.model_validate({**base, "status": "succeeded"})
    parsed = GatewaySettlementV1.model_validate(
        {
            **base,
            "status": "succeeded",
            "productVersionId": uuid4(),
            "uuSha256": "a" * 64,
        },
    )
    assert parsed.status == "succeeded"


def test_state_machine_active_sets_match_approved_partial_unique_predicates():
    assert {state.value for state in DISPATCH_ACTIVE} == {
        "pending_delivery",
        "delivering",
        "dispatched",
        "running",
    }
    assert {state.value for state in ATTEMPT_ACTIVE} == {
        "registered",
        "running",
        "received",
        "processing",
    }
    assert can_transition(DispatchState.PENDING_DELIVERY, DispatchState.DELIVERING)
    assert not can_transition(DispatchState.COMPLETED, DispatchState.RUNNING)
    assert can_transition(AttemptState.PROCESSING, AttemptState.PERSISTED)
    assert can_transition(SettlementState.FAILED, SettlementState.DELIVERING)
    assert not can_transition(ItemState.SUCCEEDED, ItemState.RUNNING)


def test_manual_target_normalization_is_explicit_and_does_not_guess_urls():
    direct = normalize_manual_target(
        ProductCollectionRequestCreate.model_validate(
            {
                "submission_key": uuid4(),
                "source": {
                    "kind": "manual",
                    "targets": [
                        {
                            "platform": "douyin",
                            "product_id_or_supported_url": "3832497447662387684",
                        },
                    ],
                },
            },
        ).source.targets[0],
    )
    assert direct.source_product_id == "3832497447662387684"

    request = ProductCollectionRequestCreate.model_validate(
        {
            "submission_key": uuid4(),
            "source": {
                "kind": "manual",
                "targets": [
                    {
                        "platform": "pinduoduo",
                        "product_id_or_supported_url": (
                            "https://mobile.yangkeduo.com/goods.html?goods_id=987363177091"
                        ),
                    },
                    {
                        "platform": "pinduoduo",
                        "product_id_or_supported_url": "987363177091",
                    },
                ],
            },
        },
    )
    assert [item.source_product_id for item in distinct_targets(request.source.targets)] == [
        "987363177091",
    ]

    unsupported = ProductCollectionRequestCreate.model_validate(
        {
            "submission_key": uuid4(),
            "source": {
                "kind": "manual",
                "targets": [
                    {
                        "platform": "douyin",
                        "product_id_or_supported_url": "https://example.test/product/3832497447662387684",
                    },
                ],
            },
        },
    )
    with pytest.raises(ProductCollectionTargetUnsupportedError):
        normalize_manual_target(unsupported.source.targets[0])
