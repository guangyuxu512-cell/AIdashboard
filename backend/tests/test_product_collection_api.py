from fastapi.testclient import TestClient

from app.main import create_app


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
