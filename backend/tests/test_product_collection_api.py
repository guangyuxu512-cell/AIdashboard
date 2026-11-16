from datetime import UTC, datetime, timedelta
from unittest.mock import create_autospec
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings, get_settings
from app.main import create_app
from app.modules.product_collection.contracts import ControlIngestV1
from app.modules.product_collection.ingest_service import ProductCollectionIngestService
from app.modules.product_collection.internal_api import get_ingest_service


def test_human_collection_and_library_routes_require_session_before_database() -> None:
    application = create_app()
    with TestClient(application) as client:
        for path in (
            "/api/v1/product-collection/requests",
            "/api/v1/product-collection/requests/11111111-1111-1111-1111-111111111111",
            "/api/v1/product-library/groups",
            "/api/v1/product-library/products",
            "/api/v1/product-library/products/11111111-1111-1111-1111-111111111111",
        ):
            response = client.get(path)
            assert response.status_code == 401
            assert response.json()["code"] == "HUMAN_AUTHENTICATION_REQUIRED"
        response = client.post(
            "/api/v1/product-collection/requests",
            json={},
        )
        assert response.status_code == 401


def test_internal_registration_requires_service_auth_before_database() -> None:
    application = create_app()
    with TestClient(application) as client:
        response = client.post(
            "/internal/mobile-collection/v1/attempts/register",
            headers={"Idempotency-Key": "synthetic"},
            json={},
        )
    assert response.status_code == 503
    assert response.json()["code"] == "PRODUCT_COLLECTION_CONFIGURATION_UNAVAILABLE"


def test_phone_ingest_requires_batch_credential_before_database() -> None:
    application = create_app()
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/mobile-collection/ingest/11111111-1111-1111-1111-111111111111",
            content=b"{}",
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 401
    assert response.json()["code"] == "PRODUCT_COLLECTION_SERVICE_AUTHENTICATION_FAILED"


@pytest.mark.parametrize("refresh", [False, True])
def test_phone_credential_handoff_is_noncacheable_and_service_authenticated(refresh) -> None:
    application = create_app()
    settings = Settings(
        _env_file=None,
        product_collection_service_token="synthetic-service-token",
        product_collection_ingest_hmac_key="synthetic-hmac-secret-at-least-32-bytes",
        product_collection_public_base_url="https://central.example.test",
    )
    attempt_id, credential_id = uuid4(), uuid4()
    control = ControlIngestV1(
        protocol="central_ingest_v1",
        attemptId=attempt_id,
        uploadUrl=f"https://central.example.test/api/v1/mobile-collection/ingest/{attempt_id}",
        credential="synthetic-batch-credential-which-is-not-a-service-token",
        credentialId=credential_id,
        expiresAt=datetime.now(UTC) + timedelta(minutes=5),
    )
    service = create_autospec(ProductCollectionIngestService, instance=True)
    service.register_attempt.return_value = control
    service.refresh_credential.return_value = control
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_ingest_service] = lambda: service
    body = {
        "schemaVersion": 1,
        "gatewayId": "synthetic-gateway",
        "gatewayJobId": "synthetic-job",
        "deviceId": "synthetic-device",
        "captureBatchId": "synthetic-batch",
    }
    if refresh:
        path = f"/internal/mobile-collection/v1/attempts/{attempt_id}/credentials/refresh"
        body["credentialId"] = str(credential_id)
        operation = service.refresh_credential
    else:
        path = "/internal/mobile-collection/v1/attempts/register"
        body.update({
            "dispatchId": str(uuid4()), "externalJobId": "synthetic-dispatch",
            "sourcePlatform": "douyin", "sourceProductId": "3797024140330926544",
            "leaseExpiresAt": (datetime.now(UTC) + timedelta(minutes=15)).isoformat(),
        })
        operation = service.register_attempt
    headers = {"Idempotency-Key": "synthetic-gateway:synthetic-job:synthetic-batch"}
    # No lifespan: these boundary tests never start background consumers.
    client = TestClient(application)
    try:
        rejected = client.post(path, json=body, headers={
            **headers, "Authorization": f"Bearer {control.credential}",
        })
        assert rejected.status_code == 401
        operation.assert_not_called()
        response = client.post(path, json=body, headers={
            **headers, "Authorization": "Bearer synthetic-service-token",
        })
    finally:
        client.close()
    assert response.status_code == (200 if refresh else 201)
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"ok": True, "controlIngest": control.model_dump(mode="json")}
    operation.assert_called_once()
    assert "synthetic-service-token" not in response.text
    assert "synthetic-hmac-secret" not in response.text
