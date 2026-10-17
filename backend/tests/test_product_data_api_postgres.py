"""Route/finite executor integration using synthetic pages and guarded PG."""

from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import install_exception_handlers
from app.modules.product_data import api
from app.modules.product_data.executor import ProductDataExecutor
from app.modules.product_data.exceptions import ProductDataCollectionLimitExceededError
from app.modules.product_data.models import ShopProductDataGeneration as Generation, ShopProductDataMetricSnapshot as Snapshot
from app.platforms.douyin.product_data import CompassProductDataPage
from app.platforms.exceptions import PlatformRequestTimeoutError
from tests.test_product_data_service_postgres import graph, submit, complete, query, publish


pytestmark = pytest.mark.integration


@pytest.fixture
def api_client(graph, monkeypatch):
    # No application lifespan, server listener, scheduler or default DB factory.
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(api.router)
    app.dependency_overrides[api.get_product_data_actor] = lambda: graph.actors[0]
    app.dependency_overrides[api.get_product_data_service] = lambda: graph.service
    app.dependency_overrides[get_database_session] = lambda: graph.session
    queued = []
    monkeypatch.setattr(api, "execute_product_data_collection", lambda *ids: queued.append(ids))
    yield SimpleNamespace(client=TestClient(app), app=app, queued=queued)


def test_explicit_post_only_once_replay_and_read_are_no_io(api_client, graph):
    body = {"shop_id": str(graph.shops[0].shop_id), "period": "1d", "submission_key": str(uuid4())}
    response = api_client.client.post("/api/v1/product-data/collections", json=body)
    assert response.status_code == 202
    first = response.json()
    assert first["status"] == "running" and first["expected_total"] is None and first["received_total"] is None
    assert len(api_client.queued) == 1
    replay = api_client.client.post("/api/v1/product-data/collections", json=body)
    assert replay.status_code == 202 and replay.json() == first and len(api_client.queued) == 1
    read = api_client.client.get("/api/v1/product-data/collections/" + first["generation_id"])
    assert read.status_code == 200 and read.json() == first and len(api_client.queued) == 1
    assert not {"lease_id", "requested_by_user_id", "requested_team_id", "payload", "cookies"} & set(first)


def test_get_uses_page_contract_and_validates_ranges_without_echo(api_client, graph):
    receipt = publish(graph)
    params = {"period": "1d", "start_date": str(receipt.scope.start_date), "end_date": str(receipt.scope.end_date)}
    response = api_client.client.get("/api/v1/product-data", params=params)
    assert response.status_code == 200
    assert response.json()["total"] == 25 and len(response.json()["items"]) == 20
    invalid = api_client.client.get("/api/v1/product-data", params=params | {"ranges": "[synthetic-private-invalid]"})
    assert invalid.status_code == 422 and invalid.json()["code"] == "PRODUCT_DATA_QUERY_INVALID"
    assert "synthetic-private-invalid" not in invalid.text
    unknown_unit = api_client.client.get("/api/v1/product-data", params=params | {"sort_field": "pay_amt", "sort_direction": "desc"})
    assert unknown_unit.status_code == 422
    assert unknown_unit.json()["code"] == "PRODUCT_DATA_UNIT_UNCONFIRMED"
    assert api_client.queued == []


@pytest.mark.parametrize("extra", [{"group_id": "synthetic-group"}, {"unknown": "synthetic-private-value"}])
def test_undeclared_query_dimension_is_not_silently_dropped(api_client, extra):
    result = api_client.client.get("/api/v1/product-data", params={
        "period": "1d", "start_date": "2026-01-01", "end_date": "2026-01-01", **extra})
    assert result.status_code == 422 and result.json()["code"] == "PRODUCT_DATA_QUERY_INVALID"
    assert "synthetic-private-value" not in result.text
    assert api_client.queued == []


def test_anonymous_api_is_not_an_alternate_authorization_path(api_client):
    api_client.app.dependency_overrides.pop(api.get_product_data_actor)
    result = api_client.client.get("/api/v1/product-data/collections/" + str(uuid4()))
    assert result.status_code == 401
    assert api_client.queued == []


def executor(graph, fetch):
    # Fresh ORM sessions; the outer rollback fixture still owns all synthetic data.
    factory = lambda: Session(graph.session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint")
    return ProductDataExecutor(factory, graph.settings, SimpleNamespace(page=fetch))


def test_finite_executor_publishes_only_complete_all_pages(graph):
    receipt, lease = submit(graph)
    snapshot = complete(receipt, graph.shops[0], 12)
    calls = []
    def fetch(generation_id, lease_id, number):
        assert (generation_id, lease_id) == (receipt.generation_id, lease)
        calls.append(number)
        return CompassProductDataPage(snapshot.products[(number - 1) * 10:number * 10], number, 10, snapshot.total)
    executor(graph, fetch).execute(receipt.generation_id, lease)
    graph.session.expire_all()
    assert calls == [1, 2]
    saved = graph.service.read_generation(graph.actors[0], receipt.generation_id)
    assert saved.status == "succeeded" and saved.received_pages == 2 and saved.received_total == 12
    assert graph.service.list(graph.actors[0], query(receipt)).total == 12


def test_later_page_timeout_does_not_publish_partial_or_retry(graph):
    first = publish(graph, total=1)
    receipt, lease = submit(graph)
    snapshot = complete(receipt, graph.shops[0], 12)
    calls = []
    def fetch(_generation, _lease, number):
        calls.append(number)
        if number == 2:
            raise PlatformRequestTimeoutError()
        return CompassProductDataPage(snapshot.products[:10], 1, 10, 12)
    executor(graph, fetch).execute(receipt.generation_id, lease)
    graph.session.expire_all()
    saved = graph.service.read_generation(graph.actors[0], receipt.generation_id)
    assert calls == [1, 2] and saved.status == "failed" and not saved.pages_complete
    assert saved.failure_code == "PLATFORM_TIMEOUT" and saved.expected_total == 12 and saved.received_total == 10
    assert graph.service.list(graph.actors[0], query(first)).items[0].generation_id == first.generation_id
    assert graph.session.scalar(select(func.count()).select_from(Snapshot)) == 1


def test_unexpected_exception_details_never_persist_as_failure(graph):
    receipt, lease = submit(graph)
    def fetch(*_):
        raise RuntimeError("synthetic-private-must-not-leak")
    executor(graph, fetch).execute(receipt.generation_id, lease)
    graph.session.expire_all()
    saved = graph.service.read_generation(graph.actors[0], receipt.generation_id)
    assert saved.status == "failed" and saved.failure_code == "PRODUCT_DATA_EXECUTION_FAILED"
    assert "synthetic-private" not in saved.model_dump_json()


@pytest.mark.parametrize("platform_total,receipt_total", [(229, 229), (2_147_483_648, None)])
def test_execution_limit_saves_safe_total_with_failure_and_preserves_facts(api_client, graph, platform_total, receipt_total):
    first = publish(graph, total=1)
    graph.settings = graph.settings.model_copy(update={"product_data_collection_max_pages": 20})
    graph.service.settings = graph.settings
    key = uuid4()
    receipt, lease = submit(graph, key=key, period="7d")
    code = ProductDataCollectionLimitExceededError.code
    assert not graph.service.fail(receipt.generation_id, uuid4(), code, "collection_coverage", expected_total=229)
    assert graph.service.read_generation(graph.actors[0], receipt.generation_id).expected_total is None
    snapshot = complete(receipt, graph.shops[0], 10)
    calls = []
    def fetch(_generation, _lease, number):
        calls.append(number)
        return CompassProductDataPage(snapshot.products, number, 10, platform_total)
    executor(graph, fetch).execute(receipt.generation_id, lease)
    graph.session.expire_all()
    saved = graph.service.read_generation(graph.actors[0], receipt.generation_id)
    assert calls == [1] and saved.status == "failed" and not saved.pages_complete
    assert saved.failure_code == code and saved.stage == "collection_coverage"
    assert saved.expected_total == receipt_total and saved.received_pages == 0 and saved.received_total is None
    assert saved.published_at is None
    read = api_client.client.get("/api/v1/product-data/collections/" + str(receipt.generation_id))
    assert read.status_code == 200 and read.json()["expected_total"] == receipt_total
    assert read.json()["failure_code"] == code
    replay = api_client.client.post("/api/v1/product-data/collections", json={
        "shop_id": str(graph.shops[0].shop_id), "period": "7d", "submission_key": str(key),
    })
    assert replay.status_code == 202 and replay.json() == read.json() and not api_client.queued
    assert graph.service.list(graph.actors[0], query(first)).items[0].generation_id == first.generation_id
    assert graph.service.list(graph.actors[0], query(receipt)).total == 0
    assert graph.session.scalar(select(func.count()).select_from(Snapshot)) == 1
    assert not graph.service.fail(receipt.generation_id, lease, code, "collection_coverage", expected_total=230)
    assert graph.service.read_generation(graph.actors[0], receipt.generation_id).expected_total == receipt_total


def test_limit_failure_metadata_does_not_replace_an_already_observed_total(graph):
    receipt, lease = submit(graph)
    snapshot = complete(receipt, graph.shops[0], 10)
    graph.service.note_progress(receipt.generation_id, lease, CompassProductDataPage(snapshot.products, 1, 10, 100))
    assert graph.service.fail(receipt.generation_id, lease, ProductDataCollectionLimitExceededError.code,
                              "collection_coverage", expected_total=229)
    graph.session.expire_all()
    saved = graph.service.read_generation(graph.actors[0], receipt.generation_id)
    assert saved.expected_total == 100 and saved.received_total == 10 and saved.received_pages == 1


@pytest.mark.parametrize("code,total", [
    ("PLATFORM_TIMEOUT", 229), (ProductDataCollectionLimitExceededError.code, True),
    (ProductDataCollectionLimitExceededError.code, -1), (ProductDataCollectionLimitExceededError.code, 2_147_483_648),
])
def test_failure_total_metadata_is_allowlisted_before_writing(graph, code, total):
    receipt, lease = submit(graph)
    with pytest.raises(ValueError, match="Invalid collection-limit receipt total"):
        graph.service.fail(receipt.generation_id, lease, code, "collection_coverage", expected_total=total)
    saved = graph.service.read_generation(graph.actors[0], receipt.generation_id)
    assert saved.status == "running" and saved.expected_total is None and saved.failure_code is None
