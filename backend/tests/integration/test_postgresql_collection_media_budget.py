"""Exact Feature-only fixtures, invisible to any external queue consumer."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import json
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import httpx
from pydantic import SecretStr
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_database_engine, get_database_session
from app.main import create_app
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.models import Team, TeamModuleAccess
from app.modules.access.module_access import ModuleCode
from app.modules.product_collection.api import get_product_library_actor
from app.modules.product_collection.contracts import GatewayAttemptRegistrationV1, canonical_sha256
from app.modules.product_collection.exceptions import ProductCollectionGatewayUnavailableError
from app.modules.product_collection.executor import ProductCollectionExecutor
from app.modules.product_collection.gateway import HttpProductCollectionGateway
from app.modules.product_collection.ingest_service import ProductCollectionIngestService
from app.modules.product_collection.models import (
    ProductCollectionDispatch as Dispatch, ProductCollectionItem as Item,
    ProductCollectionRequest as CollectionRequest, ProductCollectionUploadReceipt as UploadReceipt,
)
from app.modules.users.models import User
from tests.test_product_collection_media_urls import _body, COMMENTS, IMAGE_URL


pytestmark = pytest.mark.integration


@pytest.fixture
def isolated_collection():
    settings = get_settings()
    if settings.database_url is None:
        pytest.skip("Feature PostgreSQL was not configured")
    assert settings.database_url.path.lstrip("/") == "control_center_feat_mobile_product_collection_integration"
    assert not any((settings.product_collection_execution_enabled,
                    settings.product_collection_processing_enabled, settings.product_collection_settlement_enabled))
    with get_database_engine().connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == "control_center_feat_mobile_product_collection_integration"
        assert connection.scalar(text("SELECT current_user")) == "control_center_dev_user"
        assert list(connection.scalars(text("SELECT version_num FROM alembic_version"))) == ["20261020_0049"]
        assert connection.scalar(select(func.count()).select_from(Dispatch).where(Dispatch.state.in_(("pending_delivery", "delivering", "dispatched", "running")))) == 0
        assert connection.scalar(select(func.count()).select_from(Item).where(Item.state == "pending_dispatch")) == 0
        connection.rollback()
        outer = connection.begin()

        @contextmanager
        def sessions():
            # Service commits release only a savepoint. No fixture is ever
            # visible to another connection; the outer transaction rolls back.
            with Session(connection, join_transaction_mode="create_savepoint", expire_on_commit=False) as session:
                yield session

        user_id, team_id = uuid4(), uuid4()
        with sessions() as session:
            session.add(User(user_id=user_id, display_name="stage-2a1-media-budget", enabled=True))
            session.add(Team(team_id=team_id, name=f"stage-2a1-media-budget-{team_id}", enabled=True))
            session.flush()
            session.add(TeamModuleAccess(team_id=team_id, module_code=ModuleCode.PRODUCT_LIBRARY.value))
            session.commit()
        actor = ActorContext(user_id, "stage-2a1-media-budget", team_id, uuid4(), "member", DataScope.TEAM)
        application = create_app()

        def database_session():
            with sessions() as session:
                yield session

        application.dependency_overrides[get_database_session] = database_session
        application.dependency_overrides[get_product_library_actor] = lambda: actor
        client = TestClient(application)  # No lifespan/background consumers.
        try:
            yield application, client, sessions
        finally:
            client.close()
            outer.rollback()


def _settings(budget):
    return Settings(_env_file=None, product_collection_capture_max_attempts=budget,
                    product_collection_execution_enabled=True, product_collection_gateway_id="synthetic-gateway")


def _submit(client):
    response = client.post("/api/v1/product-collection/requests", json={
        "submission_key": str(uuid4()), "source": {"kind": "manual", "targets": [
            {"platform": "douyin", "product_id_or_supported_url": "3797024140330926544"},
        ]},
    })
    assert response.status_code == 202
    return UUID(response.json()["request_id"])


def _gateway(*, lose_first_response=False):
    delivered, jobs = [], {}

    def handle(request):
        assert request.url.path == "/api/v1/jobs"
        body = json.loads(request.content)
        delivered.append(body)
        existing = jobs.get(body["externalJobId"])
        reused = existing is not None
        if reused:
            assert existing == body
        else:
            jobs[body["externalJobId"]] = body
        if lose_first_response and len(delivered) == 1:
            raise httpx.ReadTimeout("synthetic lost response", request=request)
        job_id = "synthetic-job-" + body["dispatchId"]
        return httpx.Response(201, json={
            "ok": True, "gatewayId": "synthetic-gateway", "requested": 1,
            "accepted": [] if reused else [{"jobId": job_id}], "acceptedCount": 0 if reused else 1,
            "reused": [{"jobId": job_id}] if reused else [], "reusedCount": 1 if reused else 0,
            "skipped": [], "skippedCount": 0, "invalid": [], "dispatch": {
                **{key: body[key] for key in ("dispatchId", "externalJobId", "canonicalPayloadHash", "sourcePlatform", "sourceProductId", "ingestMode", "jobType")},
                "gatewayId": "synthetic-gateway", "gatewayJobId": job_id, "status": "pending", "reused": reused,
            },
        })

    adapter = HttpProductCollectionGateway(base_url="https://gateway.example.test", gateway_id="synthetic-gateway",
        control_token=SecretStr("synthetic-control"), callback_token=None, timeout_seconds=1,
        client=httpx.Client(transport=httpx.MockTransport(handle)))
    return adapter, delivered


@pytest.mark.parametrize("budget", [1, 3])
def test_api_frozen_budget_replay_finite_retry_and_explicit_recapture(isolated_collection, budget):
    application, client, sessions = isolated_collection
    one = _settings(budget)
    application.dependency_overrides[get_settings] = lambda: one
    request_id = _submit(client)
    gateway, sent = _gateway(lose_first_response=True)
    executor = ProductCollectionExecutor(session_factory=sessions, settings=one, gateway=gateway, cleaner=None)
    with pytest.raises(ProductCollectionGatewayUnavailableError):
        executor.dispatch_once()
    with sessions() as session:
        item = session.scalar(select(Item).where(Item.request_id == request_id))
        item_id, dispatch_id = item.item_id, item.current_dispatch_id
        dispatch = session.get(Dispatch, dispatch_id)
        frozen_hash = dispatch.canonical_payload_hash
        assert sent[0]["maxAttempts"] == budget and dispatch.delivery_attempts == 1
        dispatch.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    changed = _settings(4 - budget)
    application.dependency_overrides[get_settings] = lambda: changed
    executor = ProductCollectionExecutor(session_factory=sessions, settings=changed, gateway=gateway, cleaner=None)
    assert executor.dispatch_once()
    assert sent[0] == sent[1] and sent[1]["maxAttempts"] == budget
    with sessions() as session:
        item = session.get(Item, item_id)
        dispatch = session.get(Dispatch, dispatch_id)
        assert dispatch.canonical_payload_hash == frozen_hash and dispatch.delivery_attempts == 2
        assert dispatch.state == "dispatched"
        dispatch.state, dispatch.finished_at = "execution_failed", datetime.now(UTC)
        item.state, item.finished_at, item.attempt_count = "failed", dispatch.finished_at, 1
        request = session.get(CollectionRequest, request_id)
        request.status, request.finished_at = "failed", dispatch.finished_at
        session.commit()
    if budget == 3:
        # Ordinary business still permits a finite retry of the original Job.
        assert client.post(f"/api/v1/product-collection/items/{item_id}/retry").status_code == 200
        with sessions() as session:
            item, dispatch = session.get(Item, item_id), session.get(Dispatch, dispatch_id)
            assert item.attempt_count == 1 and item.current_dispatch_id == dispatch_id
            assert dispatch.state == "pending_delivery" and dispatch.canonical_payload_hash == frozen_hash
            dispatch.state, dispatch.finished_at = "execution_failed", datetime.now(UTC)
            item.state, item.finished_at, item.attempt_count = "failed", dispatch.finished_at, 3
            request = session.get(CollectionRequest, request_id)
            request.status, request.finished_at = "failed", dispatch.finished_at
            session.commit()
    # Configuration changes and repeat clicks cannot reopen an exhausted Job.
    assert client.post(f"/api/v1/product-collection/items/{item_id}/retry").status_code == 409
    assert len(sent) == 2
    normal = _settings(3)
    application.dependency_overrides[get_settings] = lambda: normal
    executor = ProductCollectionExecutor(session_factory=sessions, settings=normal, gateway=gateway, cleaner=None)
    assert client.post(f"/api/v1/product-collection/items/{item_id}/recapture").status_code == 200
    assert executor.dispatch_once()
    assert sent[2]["maxAttempts"] == 3 and sent[2]["recapture"] is True
    assert sent[2]["externalJobId"] != sent[1]["externalJobId"]
    with sessions() as session:
        old = session.get(Dispatch, dispatch_id)
        assert old.state == "execution_failed" and old.canonical_payload_hash == frozen_hash
        assert old.delivery_attempts == 2 and session.get(Item, item_id).attempt_count == budget


def test_v2_signed_media_api_receipt_preserves_hash_and_rejects_credentials(isolated_collection):
    application, client, sessions = isolated_collection
    settings = _settings(1)
    application.dependency_overrides[get_settings] = lambda: settings
    request_id = _submit(client)
    gateway, sent = _gateway()
    assert ProductCollectionExecutor(session_factory=sessions, settings=settings, gateway=gateway, cleaner=None).dispatch_once()
    with sessions() as session:
        item = session.scalar(select(Item).where(Item.request_id == request_id))
        dispatch = session.get(Dispatch, item.current_dispatch_id)
        registration = GatewayAttemptRegistrationV1(
            schemaVersion=1, dispatchId=dispatch.dispatch_id, gatewayId=dispatch.gateway_id,
            externalJobId=dispatch.external_job_id, gatewayJobId=dispatch.gateway_job_id,
            deviceId="synthetic-device", captureBatchId="synthetic-batch", sourcePlatform="douyin",
            sourceProductId=item.source_product_id, leaseExpiresAt=datetime.now(UTC) + timedelta(minutes=15))
        control = ProductCollectionIngestService(session).register_attempt(registration,
            secret=b"synthetic-gate-secret-at-least-32-bytes", key_id="synthetic-key",
            public_base_url="https://central.example.test", token_ttl_seconds=600, accept_grace_seconds=600)
    body = _body(f"{COMMENTS}.comment_medias_arr.*.media_image_src", IMAGE_URL)
    body["taskContext"]["jobId"] = registration.gateway_job_id
    raw = json.dumps(body).encode()
    route = f"/api/v1/mobile-collection/ingest/{control.attempt_id}"
    headers = {"Authorization": f"Bearer {control.credential}", "Content-Type": "application/json"}
    invalid = {**body, "detailBody": {"Cookie": "synthetic-forbidden"}}
    rejected = client.post(route, content=json.dumps(invalid).encode(), headers=headers)
    assert rejected.status_code == 422 and rejected.json()["code"] == "PRODUCT_COLLECTION_PAYLOAD_INVALID"
    assert "synthetic-forbidden" not in rejected.text
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(UploadReceipt)) == 0
    response = client.post(route, content=raw, headers=headers)
    assert response.status_code == 202 and response.json()["receipt"]["status"] == "received"
    duplicate = client.post(route, content=raw, headers=headers)
    assert duplicate.status_code == 202 and duplicate.json()["receipt"]["status"] == "duplicate"
    assert response.json()["receipt"]["receiptId"] == duplicate.json()["receipt"]["receiptId"]
    with sessions() as session:
        receipt = session.get(UploadReceipt, UUID(response.json()["receipt"]["receiptId"]))
        assert receipt.raw_payload == body and receipt.raw_format_version == 2
        assert receipt.content_sha256 == canonical_sha256(body)
        assert session.scalar(select(func.count()).select_from(UploadReceipt)) == 1
