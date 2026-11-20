from fastapi.testclient import TestClient

from app.main import create_app


def test_retired_central_selection_endpoints_are_not_registered():
    application = create_app()
    client = TestClient(application)
    try:
        for path in (
            "/api/v1/product-selection/categories?shop_id=11111111-1111-1111-1111-111111111111",
            "/api/v1/product-selection/candidates",
            "/api/v1/product-selection/capabilities",
            "/api/v1/product-selection/runs",
            "/api/v1/product-selection/strategies",
            "/api/v1/product-selection/strategies/11111111-1111-1111-1111-111111111111",
            "/api/v1/product-selection/runs/11111111-1111-1111-1111-111111111111",
            "/api/v1/product-selection/observations/11111111-1111-1111-1111-111111111111",
        ):
            response = client.get(path)
            assert response.status_code == 404
        assert client.post("/api/v1/product-selection/runs", json={}).status_code == 404
        assert client.post("/api/v1/product-selection/strategies", json={}).status_code == 404
    finally:
        client.close()
