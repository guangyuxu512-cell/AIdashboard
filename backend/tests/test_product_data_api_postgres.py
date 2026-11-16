"""Historical product-metric read API on guarded PostgreSQL."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.core.database import get_database_session
from app.core.exceptions import install_exception_handlers
from app.modules.product_data import api
from tests.test_product_data_service_postgres import graph, publish


pytestmark = pytest.mark.integration


@pytest.fixture
def api_client(graph):
    # No application lifespan, server listener, scheduler or default DB factory.
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(api.router)
    app.dependency_overrides[api.get_product_data_actor] = lambda: graph.actors[0]
    app.dependency_overrides[api.get_product_data_service] = lambda: graph.service
    app.dependency_overrides[get_database_session] = lambda: graph.session
    yield SimpleNamespace(client=TestClient(app), app=app)


def test_get_uses_page_contract_and_validates_ranges_without_echo(api_client, graph):
    receipt = publish(graph)
    params = {"period": "1d", "start_date": str(receipt.scope.start_date), "end_date": str(receipt.scope.end_date)}
    response = api_client.client.get("/api/v1/product-data", params=params)
    assert response.status_code == 200
    assert response.json()["total"] == 25 and len(response.json()["items"]) == 20
    invalid = api_client.client.get("/api/v1/product-data", params=params | {"ranges": "[synthetic-private-invalid]"})
    assert invalid.status_code == 422 and invalid.json()["code"] == "PRODUCT_DATA_QUERY_INVALID"
    assert "synthetic-private-invalid" not in invalid.text
    amount_sort = api_client.client.get("/api/v1/product-data", params=params | {"sort_field": "pay_amt", "sort_direction": "desc"})
    assert amount_sort.status_code == 200 and amount_sort.json()["coverage"]["unit_unconfirmed_codes"] == []
    assert amount_sort.json()["items"][0]["metrics"]["pay_amt"]["unit_verified"] is True
    legacy = api_client.client.get("/api/v1/product-data", params=params | {"sort_field": "receive_amt", "sort_direction": "desc"})
    assert legacy.status_code == 422 and legacy.json()["code"] == "PRODUCT_DATA_QUERY_INVALID"


@pytest.mark.parametrize("extra", [{"group_id": "synthetic-group"}, {"unknown": "synthetic-private-value"}])
def test_undeclared_query_dimension_is_not_silently_dropped(api_client, extra):
    result = api_client.client.get("/api/v1/product-data", params={
        "period": "1d", "start_date": "2026-01-01", "end_date": "2026-01-01", **extra})
    assert result.status_code == 422 and result.json()["code"] == "PRODUCT_DATA_QUERY_INVALID"
    assert "synthetic-private-value" not in result.text


def test_anonymous_api_is_not_an_alternate_authorization_path(api_client):
    api_client.app.dependency_overrides.pop(api.get_product_data_actor)
    result = api_client.client.get("/api/v1/product-data", params={"period": "1d", "start_date": "2026-01-01", "end_date": "2026-01-01"})
    assert result.status_code == 401
