"""Feature-only cancellation generation tests; no real gateway or device I/O."""

from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_database_engine
from app.modules.access.models import Team, TeamModuleAccess
from app.modules.access.module_access import ModuleCode
from app.modules.product_collection.api import get_product_library_actor
from app.modules.product_collection.dispatch_service import ProductCollectionDispatchService, build_dispatch_command
from app.modules.product_collection.cleaner import ExistingUuProductPackageCleaner
from app.modules.product_collection.contracts import canonical_sha256
from app.modules.product_collection.executor import ProductCollectionExecutor
from app.modules.product_collection.human_service import ProductCollectionHumanService
from app.modules.product_collection.models import (
    ProductCollectionDispatch as Dispatch,
    ProductCollectionItem as Item,
    ProductCollectionRequest as CollectionRequest,
    ProductCollectionUploadReceipt as UploadReceipt,
    ProductCollectionPersistReceipt as PersistReceipt,
    ProductLibraryProductVersion as ProductVersion,
)
from app.modules.product_collection.ports import GatewayCancelResult, GatewayDispatchResult, GatewayJobState
from app.modules.users.models import User
from tests.integration.test_postgresql_collection_media_budget import (
    isolated_collection, _settings,
)


pytestmark = pytest.mark.integration


class Gateway:
    def __init__(self, job_id=None):
        self.job_id = job_id
        self.delivered = []
        self.canceled = []
        self.settled = []

    def deliver(self, command):
        self.delivered.append(command)
        return GatewayDispatchResult(
            gateway_id="synthetic-gateway", gateway_job_id=self.job_id or f"job-{command.dispatch_id}",
            external_job_id=command.external_job_id, status="pending", reused=False,
        )

    def cancel(self, *, gateway_job_id):
        self.canceled.append(gateway_job_id)
        return GatewayCancelResult(gateway_job_id=gateway_job_id, status="canceled")

    def status(self, *, gateway_job_id, external_job_id):
        command = next(c for c in self.delivered if c.external_job_id == external_job_id)
        return GatewayJobState("synthetic-gateway", gateway_job_id, external_job_id,
            command.source_platform.value, command.source_product_id, None, "pending", 0, command.max_attempts)

    def settle(self, settlement):
        self.settled.append(settlement)


def failed_history(application, client, sessions, *, sibling=False, product_id="3797024140330926544"):
    application.dependency_overrides[get_settings] = lambda: _settings(1)
    targets = [{"platform": "douyin", "product_id_or_supported_url": product_id}]
    if sibling:
        targets.append({"platform": "douyin", "product_id_or_supported_url": "9000000000000000001"})
    result = client.post("/api/v1/product-collection/requests", json={
        "submission_key": str(uuid4()), "source": {"kind": "manual", "targets": targets},
    })
    assert result.status_code == 202
    request_id = UUID(result.json()["request_id"])
    with sessions() as session:
        assert ProductCollectionDispatchService(session).plan_pending(gateway_id="synthetic-gateway") == len(targets)
        item = session.scalar(select(Item).where(Item.request_id == request_id, Item.source_product_id == product_id))
        dispatch = session.get(Dispatch, item.current_dispatch_id)
        request = session.get(CollectionRequest, request_id)
        canceled_at = session.scalar(select(func.clock_timestamp()))
        item.state, item.finished_at, item.attempt_count = "failed", canceled_at, 1
        dispatch.state, dispatch.finished_at, dispatch.delivery_attempts = "delivery_failed", canceled_at, 1
        request.cancel_requested_at = canceled_at
        request.cancel_requested_by_user_id = request.requested_by_user_id
        request.status, request.finished_at = ("running", None) if sibling else ("failed", canceled_at)
        session.commit()
        return request_id, item.item_id, dispatch.dispatch_id, canceled_at


@pytest.mark.parametrize("cancel_again", [False, True])
def test_old_cancel_does_not_consume_recapture_and_new_cancel_still_applies(isolated_collection, cancel_again):
    application, client, sessions = isolated_collection
    request_id, item_id, old_id, old_cancel = failed_history(application, client, sessions)
    result = client.post(f"/api/v1/product-collection/items/{item_id}/recapture")
    assert result.status_code == 200 and result.json()["status"] == "running"
    gateway = Gateway()
    with sessions() as session:
        item = session.get(Item, item_id)
        current = session.get(Dispatch, item.current_dispatch_id)
        request = session.get(CollectionRequest, request_id)
        new_id = current.dispatch_id
        assert new_id != old_id and current.created_at > old_cancel
        assert current.delivery_attempts == 0 and current.gateway_job_id is None
        assert request.cancel_requested_at == old_cancel
        assert session.get(Dispatch, old_id).state == "delivery_failed"
        session.rollback()
    with sessions() as session:
        assert not ProductCollectionDispatchService(session).cancel_requested_once(gateway)
    with sessions() as session:
        assert ProductCollectionDispatchService(session).deliver_once(
            gateway, lease_seconds=60, max_attempts=1, retry_delay_seconds=1,
        )
    assert len(gateway.delivered) == 1 and gateway.delivered[0].recapture is True
    assert gateway.canceled == []
    if cancel_again:
        result = client.post(f"/api/v1/product-collection/requests/{request_id}/cancel")
        assert result.status_code == 200
        with sessions() as session:
            assert ProductCollectionDispatchService(session).cancel_requested_once(gateway)
        final = client.get(f"/api/v1/product-collection/requests/{request_id}").json()
        assert final["status"] == "canceled" and final["items"][0]["state"] == "canceled"
        assert len(gateway.canceled) == 1
    with sessions() as session:
        assert session.get(Dispatch, old_id).state == "delivery_failed"
        assert session.scalar(select(func.count()).select_from(Dispatch).where(Dispatch.item_id == item_id)) == 2


def test_recapture_keeps_old_cancel_effective_for_other_items(isolated_collection):
    application, client, sessions = isolated_collection
    request_id, item_id, old_id, old_cancel = failed_history(application, client, sessions, sibling=True)
    assert client.post(f"/api/v1/product-collection/items/{item_id}/recapture").status_code == 200
    gateway = Gateway()
    with sessions() as session:
        assert ProductCollectionDispatchService(session).cancel_requested_once(gateway)
    with sessions() as session:
        assert not ProductCollectionDispatchService(session).cancel_requested_once(gateway)
        items = list(session.scalars(select(Item).where(Item.request_id == request_id)))
        assert {i.state for i in items if i.item_id != item_id} == {"canceled"}
        assert session.get(Item, item_id).state == "dispatching"
        assert session.get(CollectionRequest, request_id).cancel_requested_at == old_cancel
        assert session.get(Dispatch, old_id).state == "delivery_failed"
    assert gateway.canceled == []  # Undelivered sibling canceled without external I/O.


def test_member_recapture_authorization_and_active_dedup_are_unchanged(isolated_collection):
    application, client, sessions = isolated_collection
    request_id, item_id, old_id, old_cancel = failed_history(application, client, sessions)
    actor = application.dependency_overrides[get_product_library_actor]()
    other_team = uuid4()
    with sessions() as session:
        session.add(Team(team_id=other_team, name=f"recapture-other-{other_team}", enabled=True))
        session.flush()
        session.add(TeamModuleAccess(team_id=other_team, module_code=ModuleCode.PRODUCT_LIBRARY.value))
        session.commit()
    application.dependency_overrides[get_product_library_actor] = lambda: replace(actor, team_id=other_team)
    assert client.post(f"/api/v1/product-collection/items/{item_id}/recapture").status_code == 404
    application.dependency_overrides[get_product_library_actor] = lambda: actor
    with sessions() as session:
        grant = session.scalar(select(TeamModuleAccess).where(
            TeamModuleAccess.team_id == actor.team_id, TeamModuleAccess.module_code == ModuleCode.PRODUCT_LIBRARY.value,
        ))
        session.delete(grant)
        session.commit()
    assert client.post(f"/api/v1/product-collection/items/{item_id}/recapture").status_code == 403
    with sessions() as session:
        session.add(TeamModuleAccess(team_id=actor.team_id, module_code=ModuleCode.PRODUCT_LIBRARY.value))
        session.commit()
    assert client.post(f"/api/v1/product-collection/items/{item_id}/recapture").status_code == 200
    assert client.post(f"/api/v1/product-collection/items/{item_id}/recapture").status_code == 409
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Dispatch).where(Dispatch.item_id == item_id)) == 2
        request = session.get(CollectionRequest, request_id)
        assert request.cancel_requested_at == old_cancel and request.cancel_requested_by_user_id == actor.user_id


def test_normal_cancel_before_initial_dispatch_remains_effective(isolated_collection):
    application, client, sessions = isolated_collection
    application.dependency_overrides[get_settings] = lambda: _settings(1)
    response = client.post("/api/v1/product-collection/requests", json={
        "submission_key": str(uuid4()), "source": {"kind": "manual", "targets": [
            {"platform": "douyin", "product_id_or_supported_url": "3797024140330926544"},
        ]},
    })
    request_id = UUID(response.json()["request_id"])
    canceled = client.post(f"/api/v1/product-collection/requests/{request_id}/cancel")
    assert canceled.status_code == 200 and canceled.json()["status"] == "canceled"
    with sessions() as session:
        assert ProductCollectionDispatchService(session).plan_pending(gateway_id="synthetic-gateway") == 0


def test_recapture_failure_rolls_back_new_dispatch_and_preserves_old_cancel(isolated_collection, monkeypatch):
    application, client, sessions = isolated_collection
    request_id, item_id, old_id, old_cancel = failed_history(application, client, sessions)
    actor = application.dependency_overrides[get_product_library_actor]()
    with sessions() as session:
        service = ProductCollectionHumanService(session)

        def fail_after_dispatch_insert(**kwargs):
            raise RuntimeError("synthetic post-insert failure")

        monkeypatch.setattr(service.repository, "current_product", fail_after_dispatch_insert)
        with pytest.raises(RuntimeError, match="synthetic post-insert failure"):
            service.recapture_item(actor, item_id, gateway_id="synthetic-gateway", max_capture_attempts=1)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Dispatch).where(Dispatch.item_id == item_id)) == 1
        assert session.get(Item, item_id).current_dispatch_id == old_id
        assert session.get(Item, item_id).state == "failed"
        request = session.get(CollectionRequest, request_id)
        assert request.status == "failed" and request.cancel_requested_at == old_cancel


@pytest.mark.parametrize("name,expected_hash,normalized_hash", [
    ("capture-private.json", "b3e8ed3360ac9e53005a7b51887761a3868bbae4cbd55e63702c425c829ed768",
        "3a90defc4892d34ce9da95c12f62450d12d44abc5033290db46cfcf1398cd2b3"),
    ("capture-retest-private.json", "e544b9f48878f72769cd43fba7c5f40f6e435d996e7e2218784e9b221fc5d217",
        "9d68cbf250c12da7c0941f0163f0bc272efaebdf714d4a7a69d275d8dc55e625"),
])
def test_recapture_real_package_via_formal_ingest_real_cleaner_and_status_outbox(
    isolated_collection, monkeypatch, record_property, name, expected_hash, normalized_hash,
):
    """Real retained V2 input + services/PG/cleaner; gateway/device are synthetic."""
    private_dir = os.environ.get("PRODUCT_COLLECTION_TEST_PRIVATE_PACKAGES")
    cleaner_path = os.environ.get("PRODUCT_COLLECTION_TEST_CLEANER_MODULE")
    if not private_dir or not cleaner_path:
        pytest.skip("Protected retained package and existing cleaner module were not configured")
    application, client, sessions = isolated_collection
    source = Path(private_dir) / name
    raw = source.read_bytes()
    observed_hash = sha256(raw).hexdigest()
    assert observed_hash == expected_hash
    record_property("sample_sha256", observed_hash)
    body = json.loads(raw)
    product_id = body["taskContext"]["sourceProductId"]
    request_id, item_id, old_id, old_cancel = failed_history(
        application, client, sessions, product_id=product_id,
    )
    assert client.post(f"/api/v1/product-collection/items/{item_id}/recapture").status_code == 200
    settings = _settings(1).model_copy(update={
        "product_collection_processing_enabled": True, "product_collection_settlement_enabled": True,
        "product_collection_service_token": SecretStr("synthetic-service-token"),
        "product_collection_ingest_hmac_key": SecretStr("synthetic-ingest-secret-at-least-32-bytes"),
        "product_collection_public_base_url": "https://central.example.test",
    })
    application.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr(get_database_engine(), "hide_parameters", True)
    gateway = Gateway(job_id=body["taskContext"]["jobId"])
    cleaner = ExistingUuProductPackageCleaner(type(settings)(
        _env_file=None, product_collection_cleaner_module_path=Path(cleaner_path),
    ))
    executor = ProductCollectionExecutor(session_factory=sessions, settings=settings, gateway=gateway, cleaner=cleaner)
    assert executor.dispatch_once() and len(gateway.delivered) == 1
    with sessions() as session:
        dispatch = session.get(Dispatch, session.get(Item, item_id).current_dispatch_id)
        registration = {
            "schemaVersion": 1, "dispatchId": str(dispatch.dispatch_id), "gatewayId": dispatch.gateway_id,
            "externalJobId": dispatch.external_job_id, "gatewayJobId": dispatch.gateway_job_id,
            "deviceId": "synthetic-recapture-device", "captureBatchId": body["taskContext"]["captureBatchId"],
            "sourcePlatform": "douyin", "sourceProductId": product_id,
            "leaseExpiresAt": (session.scalar(select(func.clock_timestamp())) + timedelta(minutes=15)).isoformat(),
        }
    registered = client.post("/internal/mobile-collection/v1/attempts/register", json=registration, headers={
        "Authorization": "Bearer synthetic-service-token", "Idempotency-Key":
            f"{registration['gatewayId']}:{registration['gatewayJobId']}:{registration['captureBatchId']}",
    })
    assert registered.status_code == 201
    record_property("register_http", registered.status_code)
    control = registered.json()["controlIngest"]
    headers = {"Authorization": f"Bearer {control['credential']}", "Content-Type": "application/json"}
    route = urlsplit(control["uploadUrl"]).path
    received = client.post(route, content=raw, headers=headers)
    assert received.status_code == 202
    receipt_id = UUID(received.json()["receipt"]["receiptId"])
    record_property("ingest_http", received.status_code)
    record_property("upload_receipt_id", str(receipt_id))
    assert received.json()["receipt"]["status"] == "received"
    with sessions() as session:
        receipt = session.get(UploadReceipt, receipt_id)
        stored_hash = canonical_sha256(receipt.raw_payload)
        # Existing model defaults (e.g. recaptureRequested=false) are not a file rewrite.
        assert stored_hash == normalized_hash and receipt.content_sha256 == normalized_hash
        original_keys = ("detailBody", "skuBody", "detailSha256", "skuSha256", "sha256")
        original_fields_hash = canonical_sha256({key: body[key] for key in original_keys})
        stored_fields_hash = canonical_sha256({key: receipt.raw_payload[key] for key in original_keys})
        assert stored_fields_hash == original_fields_hash and receipt.raw_format_version == 2
        assert receipt.state == "received" and receipt.gateway_settlement_state is None
    assert executor.process_once()
    with sessions() as session:
        receipt = session.get(UploadReceipt, receipt_id)
        assert receipt.state == "persisted" and receipt.gateway_settlement_state == "pending"
        assert session.scalar(select(func.count()).select_from(PersistReceipt).where(PersistReceipt.upload_receipt_id == receipt_id)) == 1
        assert session.scalar(select(func.count()).select_from(ProductVersion)) == 1
        persisted = session.scalar(select(PersistReceipt).where(PersistReceipt.upload_receipt_id == receipt_id))
        version = session.get(ProductVersion, persisted.version_id)
        counts = (len(version.uu_snapshot["goodsInfo"]["skuInfoMap"]),
                  len(version.uu_snapshot["goodsInfo"]["goodsImageList"]),
                  len(version.uu_snapshot["goodsDetailInfo"]["detail_imgs"]))
        assert counts == (7, 12, 18)
        record_property("persist_receipt_id", str(persisted.persist_receipt_id))
        record_property("product_version_id", str(persisted.version_id))
        record_property("product_id", str(persisted.product_id))
        record_property("cleaned_counts", "7 SKU / 12 main / 18 detail")
    duplicate = client.post(route, content=raw, headers=headers)
    assert duplicate.status_code == 202 and duplicate.json()["receipt"]["status"] == "duplicate"
    assert duplicate.json()["receipt"]["receiptId"] == str(receipt_id)
    assert not executor.process_once()
    assert executor.settle_once() and not executor.settle_once()
    assert len(gateway.settled) == 1
    settlement = gateway.settled[0]
    assert settlement.status == "succeeded" and settlement.receipt_id == receipt_id
    assert settlement.job_id == registration["gatewayJobId"]
    assert set(settlement.model_dump(by_alias=True)) == {
        "schemaVersion", "dispatchId", "gatewayId", "externalJobId", "gatewayJobId", "captureBatchId",
        "deviceId", "sourcePlatform", "sourceProductId", "attemptId", "receiptId", "status", "errorCode",
        "errorMessage", "productVersionId", "uuSha256", "persistedAt",
    }
    with sessions() as session:
        assert session.get(UploadReceipt, receipt_id).gateway_settlement_state == "settled"
        record_property("settlement_state", "settled (synthetic gateway)")
        assert session.get(CollectionRequest, request_id).cancel_requested_at == old_cancel
        assert session.get(Dispatch, old_id).state == "delivery_failed"
    assert client.get(f"/api/v1/product-collection/requests/{request_id}").json()["status"] == "succeeded"
    products = client.get("/api/v1/product-library/products")
    assert products.status_code == 200 and products.json()["total"] == 1
    final_file_hash = sha256(source.read_bytes()).hexdigest()
    assert final_file_hash == expected_hash


def test_uncommitted_recapture_locks_out_concurrent_recapture_and_cancel(isolated_collection):
    """Publish only terminal fixtures; a running dispatch is never visible to consumers."""
    application, _, _ = isolated_collection  # Reuse exact Feature DB/head/disabled-consumer guards.
    actor = application.dependency_overrides[get_product_library_actor]()
    user_id, team_id, request_id, item_id, old_id = (uuid4() for _ in range(5))
    actor = replace(actor, user_id=user_id, team_id=team_id)
    engine = get_database_engine()
    try:
        with Session(engine, expire_on_commit=False) as seed:
            seed.add(User(user_id=user_id, display_name="recapture-lock-test", enabled=True))
            seed.add(Team(team_id=team_id, name=f"recapture-lock-{team_id}", enabled=True))
            seed.flush()
            seed.add(TeamModuleAccess(team_id=team_id, module_code=ModuleCode.PRODUCT_LIBRARY.value))
            now = seed.scalar(select(func.clock_timestamp()))
            seed.add(CollectionRequest(
                request_id=request_id, team_id=team_id, requested_by_user_id=user_id,
                submission_key=uuid4(), source_kind="manual", canonical_request_hash="a" * 64,
                status="failed", item_count=1, cancel_requested_at=now,
                cancel_requested_by_user_id=user_id, finished_at=now,
            ))
            seed.flush()
            item = Item(item_id=item_id, request_id=request_id, team_id=team_id, platform="douyin",
                source_product_id="3797024140330926544", collection_mode="auto_gateway", state="failed",
                attempt_count=1, finished_at=now)
            seed.add(item)
            seed.flush()
            command = build_dispatch_command(old_id, item, max_attempts=1)
            seed.add(Dispatch(dispatch_id=old_id, item_id=item_id, team_id=team_id, dispatch_no=1,
                external_job_id=command.external_job_id, canonical_payload_hash=command.canonical_payload_hash,
                gateway_id="synthetic-gateway", state="delivery_failed", delivery_attempts=1, finished_at=now))
            seed.flush()
            item.current_dispatch_id = old_id
            seed.commit()  # All published fixture rows are already terminal.
        with engine.connect() as connection:
            outer = connection.begin()
            try:
                with Session(connection, join_transaction_mode="create_savepoint", expire_on_commit=False) as first:
                    result = ProductCollectionHumanService(first).recapture_item(
                        actor, item_id, gateway_id="synthetic-gateway", max_capture_attempts=1,
                    )
                    assert result.status == "running"
                for operation in ("recapture", "cancel"):
                    with Session(engine) as contender:
                        contender.execute(text("SET LOCAL lock_timeout = '250ms'"))
                        service = ProductCollectionHumanService(contender)
                        with pytest.raises(OperationalError) as error:
                            if operation == "recapture":
                                service.recapture_item(actor, item_id, gateway_id="synthetic-gateway", max_capture_attempts=1)
                            else:
                                service.cancel_request(actor, request_id)
                        assert getattr(error.value.orig, "sqlstate", None) == "55P03"
                with Session(engine) as observer:
                    assert observer.scalar(select(func.count()).select_from(Dispatch).where(Dispatch.item_id == item_id)) == 1
                    assert observer.get(CollectionRequest, request_id).status == "failed"
            finally:
                outer.rollback()  # Never publish the recapture to background workers.
    finally:
        # Exact synthetic identities only; no historical/user rows or queue scan.
        with Session(engine) as cleanup:
            cleanup.execute(update(Item).where(Item.item_id == item_id, Item.team_id == team_id).values(current_dispatch_id=None))
            cleanup.execute(delete(Dispatch).where(Dispatch.item_id == item_id, Dispatch.team_id == team_id))
            cleanup.execute(delete(Item).where(Item.item_id == item_id, Item.team_id == team_id))
            cleanup.execute(delete(CollectionRequest).where(CollectionRequest.request_id == request_id, CollectionRequest.team_id == team_id))
            cleanup.execute(delete(TeamModuleAccess).where(TeamModuleAccess.team_id == team_id))
            cleanup.execute(delete(Team).where(Team.team_id == team_id))
            cleanup.execute(delete(User).where(User.user_id == user_id))
            cleanup.commit()
