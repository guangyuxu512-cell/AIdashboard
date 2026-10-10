from fastapi.testclient import TestClient

from app.main import create_app


def test_read_api_requires_human_session_before_database_access():
    application = create_app()
    client = TestClient(application)
    try:
        for path in (
            "/api/v1/product-selection/candidates",
            "/api/v1/product-selection/observations/11111111-1111-1111-1111-111111111111",
        ):
            response = client.get(path)
            assert response.status_code == 401
            assert response.json()["code"] == "HUMAN_AUTHENTICATION_REQUIRED"
    finally:
        client.close()
