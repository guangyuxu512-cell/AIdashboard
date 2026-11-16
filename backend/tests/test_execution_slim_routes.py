from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.api_tokens.catalog import permissions_catalog


def test_retired_central_library_and_ai_routes_are_absent_while_worker_routes_remain() -> None:
    app = create_app()
    identifier = "11111111-1111-1111-1111-111111111111"
    with TestClient(app) as client:
        for path in (
            "/api/v1/ai-workbench/models",
            "/api/v1/ai-models",
            "/api/v1/product-library/groups",
            "/api/v1/product-library/products",
            f"/api/v1/product-library/products/{identifier}",
            "/api/v1/product-collection/requests",
            f"/api/v1/product-collection/requests/{identifier}",
            "/internal/applications/v1/shops",
            "/api/v1/product-data/collection-shops",
            f"/api/v1/product-data/collections/{identifier}",
            f"/api/v1/product-data/collection-batches/{identifier}",
        ):
            assert client.get(path).status_code == 404
        for path in (
            "/api/v1/product-collection/requests",
            "/internal/mobile-collection/v1/attempts/register",
            f"/api/v1/mobile-collection/ingest/{identifier}",
            "/api/v1/product-data/collections",
            "/api/v1/product-data/collection-batches",
        ):
            assert client.post(path, json={}).status_code == 404
        paths = app.openapi()["paths"]
        for path in (
            "/api/v1/assets",
            "/api/v1/worker/heartbeat",
            "/api/v1/worker/tasks/claim",
            "/api/v1/worker/rpa-shop-inventory",
            "/api/v1/tasks",
            "/api/v1/schedules",
            "/api/v1/product-selection/capabilities",
            "/api/v1/product-data",
            "/internal/applications/v1/worker-prechecks",
        ):
            assert path in paths
        assert not any(path.startswith("/api/v1/ai-workbench/") for path in paths)
        assert not any(path.startswith("/api/v1/ai-models") for path in paths)
        permissions = {entry["id"] for entry in permissions_catalog(app)}
        assert "GET /api/v1/product-data" in permissions
        assert not any(" /api/v1/product-data/collection" in entry for entry in permissions)
