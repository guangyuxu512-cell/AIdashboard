"""Real PostgreSQL invariants for the mobile product collection inbox/outbox."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4
import json

import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.models import Team, TeamModuleAccess, TeamShopAccess
from app.modules.access.module_access import ModuleCode
from app.modules.product_collection.contracts import (
    GatewayAttemptRegistrationV1,
    ProductCollectionRequestCreate,
)
from app.modules.product_collection.dispatch_service import (
    ProductCollectionDispatchService,
    command_from_dispatch,
)
from app.modules.product_collection.exceptions import (
    ProductCollectionLeaseLostError,
    ProductCollectionIngestCredentialError,
    ProductCollectionRequestNotFoundError,
    ProductCollectionSubmissionConflictError,
    ProductCollectionUploadConflictError,
)
from app.modules.product_collection.human_service import ProductCollectionHumanService
from app.modules.product_collection.ingest_service import ProductCollectionIngestService
from app.modules.product_collection.models import (
    ProductCollectionCaptureAttempt as CaptureAttempt,
    ProductCollectionDispatch as Dispatch,
    ProductCollectionItem as Item,
    ProductCollectionPersistReceipt as PersistReceipt,
    ProductCollectionRequest as CollectionRequest,
    ProductCollectionUploadReceipt as UploadReceipt,
    ProductLibraryGroup as LibraryGroup,
    ProductLibraryProduct as Product,
    ProductLibraryProductVersion as ProductVersion,
)
from app.modules.product_collection.ports import CleanedProductPackage
from app.modules.product_collection.service import (
    ProductCollectionProcessingService,
    ProductCollectionSettlementService,
)
from app.modules.product_collection.contracts import SourcePlatform
from app.modules.product_collection.ports import GatewayDispatchResult
from app.modules.product_selection.models import (
    ProductSelectionCandidate as SelectionCandidate,
    ProductSelectionObservation as SelectionObservation,
)
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.users.models import User


pytestmark = pytest.mark.integration
FEATURE_DATABASE = "control_center_feat_mobile_product_collection_integration"


@dataclass(frozen=True)
class Graph:
    engine: Engine
    user_id: UUID
    team_id: UUID
    request_id: UUID
    item_id: UUID
    dispatch_id: UUID
    attempt_id: UUID
    upload_receipt_id: UUID
    source_product_id: str


@dataclass(frozen=True)
class AcceptedUpload:
    request_id: UUID
    item_id: UUID
    attempt_id: UUID
    receipt_id: UUID
    credential: str
    raw: bytes
    source_product_id: str


def _cleanup(engine: Engine, *, user_id: UUID, team_id: UUID) -> None:
    with Session(engine) as session:
        assert session.scalar(text("SELECT current_database()")) == FEATURE_DATABASE
        session.execute(
            update(Product)
            .where(Product.team_id == team_id)
            .values(adopted_version_id=None),
        )
        session.execute(delete(PersistReceipt).where(PersistReceipt.team_id == team_id))
        session.execute(delete(ProductVersion).where(ProductVersion.team_id == team_id))
        session.execute(delete(UploadReceipt).where(UploadReceipt.team_id == team_id))
        session.execute(delete(CaptureAttempt).where(CaptureAttempt.team_id == team_id))
        session.execute(
            update(Item).where(Item.team_id == team_id).values(current_dispatch_id=None),
        )
        session.execute(delete(Dispatch).where(Dispatch.team_id == team_id))
        session.execute(delete(Item).where(Item.team_id == team_id))
        session.execute(delete(CollectionRequest).where(CollectionRequest.team_id == team_id))
        session.execute(delete(Product).where(Product.team_id == team_id))
        session.execute(delete(LibraryGroup).where(LibraryGroup.team_id == team_id))
        candidate_ids = select(SelectionCandidate.candidate_id).where(
            SelectionCandidate.team_id == team_id,
        )
        session.execute(
            delete(SelectionObservation).where(
                SelectionObservation.candidate_id.in_(candidate_ids),
            ),
        )
        session.execute(delete(SelectionCandidate).where(SelectionCandidate.team_id == team_id))
        session.execute(delete(TeamShopAccess).where(TeamShopAccess.team_id == team_id))
        session.execute(delete(Shop).where(Shop.owner_user_id == user_id))
        session.execute(delete(TeamModuleAccess).where(TeamModuleAccess.team_id == team_id))
        session.execute(delete(Team).where(Team.team_id == team_id))
        session.execute(delete(User).where(User.user_id == user_id))
        session.commit()


@pytest.fixture
def graph(postgresql_engine: Engine):
    with postgresql_engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == FEATURE_DATABASE
        assert connection.scalar(text("SELECT current_user")) == "control_center_dev_user"

    ids = {
        "user_id": uuid4(),
        "team_id": uuid4(),
        "request_id": uuid4(),
        "item_id": uuid4(),
        "dispatch_id": uuid4(),
        "attempt_id": uuid4(),
        "upload_receipt_id": uuid4(),
    }
    source_product_id = str(8_880_000_000_000_000_001 + ids["user_id"].int % 100_000)
    now = datetime.now(UTC)
    try:
        with Session(postgresql_engine) as session:
            session.add(
                User(
                    user_id=ids["user_id"],
                    display_name=f"pc-integration-{ids['user_id']}",
                    enabled=True,
                ),
            )
            session.add(
                Team(
                    team_id=ids["team_id"],
                    name=f"pc-integration-{ids['team_id']}",
                    enabled=True,
                ),
            )
            session.flush()
            session.add(
                TeamModuleAccess(
                    team_id=ids["team_id"],
                    module_code=ModuleCode.PRODUCT_LIBRARY.value,
                ),
            )
            request = CollectionRequest(
                request_id=ids["request_id"],
                team_id=ids["team_id"],
                requested_by_user_id=ids["user_id"],
                submission_key=uuid4(),
                source_kind="manual",
                target_group_id=None,
                canonical_request_hash="a" * 64,
                status="running",
                item_count=1,
            )
            item = Item(
                item_id=ids["item_id"],
                request_id=ids["request_id"],
                team_id=ids["team_id"],
                candidate_id=None,
                platform="douyin",
                source_product_id=source_product_id,
                collection_mode="auto_gateway",
                target_group_id=None,
                state="received",
                current_dispatch_id=None,
                library_product_id=None,
                expected_manual_revision=None,
                attempt_count=1,
            )
            session.add(request)
            session.flush()
            session.add(item)
            session.flush()
            dispatch = Dispatch(
                dispatch_id=ids["dispatch_id"],
                item_id=ids["item_id"],
                team_id=ids["team_id"],
                dispatch_no=1,
                external_job_id=f"pcd_v1_{ids['dispatch_id'].hex}",
                canonical_payload_hash="b" * 64,
                gateway_id="test-gateway",
                gateway_job_id=f"job-{ids['dispatch_id']}",
                state="running",
                delivery_attempts=1,
            )
            session.add(dispatch)
            session.flush()
            item.current_dispatch_id = dispatch.dispatch_id
            attempt = CaptureAttempt(
                attempt_id=ids["attempt_id"],
                dispatch_id=ids["dispatch_id"],
                gateway_id="test-gateway",
                team_id=ids["team_id"],
                gateway_device_id=f"device-{ids['attempt_id']}",
                gateway_job_id=dispatch.gateway_job_id,
                capture_batch_id=f"batch-{ids['attempt_id']}",
                attempt_no=1,
                ingest_credential_id=uuid4(),
                ingest_credential_version=1,
                ingest_token_key_id="test-key-v1",
                ingest_token_salt="c" * 32,
                ingest_token_hash="d" * 64,
                token_issued_at=now - timedelta(minutes=2),
                token_consumed_at=now - timedelta(minutes=1),
                token_expires_at=now + timedelta(minutes=30),
                accept_until=now + timedelta(hours=1),
                accepted_content_sha256="e" * 64,
                state="received",
                registered_at=now - timedelta(minutes=2),
            )
            upload = UploadReceipt(
                upload_receipt_id=ids["upload_receipt_id"],
                team_id=ids["team_id"],
                attempt_id=ids["attempt_id"],
                upload_key=f"upload-{ids['upload_receipt_id']}",
                content_sha256="e" * 64,
                raw_payload={
                    "eventType": "complete",
                    "detailBody": {"productId": source_product_id},
                    "skuBody": {"skus": []},
                    "capturedAt": int(now.timestamp() * 1000),
                    "taskContext": {
                        "jobId": dispatch.gateway_job_id,
                        "captureBatchId": attempt.capture_batch_id,
                        "jobType": "product",
                        "sourcePlatform": "douyin",
                        "sourceProductId": source_product_id,
                    },
                },
                raw_format_version=1,
                state="received",
                received_at=now,
            )
            session.add(attempt)
            session.flush()
            session.add(upload)
            session.commit()
        yield Graph(postgresql_engine, source_product_id=source_product_id, **ids)
    finally:
        _cleanup(
            postgresql_engine,
            user_id=ids["user_id"],
            team_id=ids["team_id"],
        )


def _claim(graph: Graph):
    with Session(graph.engine, expire_on_commit=False) as session:
        claim = ProductCollectionProcessingService(session).claim(lease_seconds=120)
        assert claim is not None
        assert claim.upload_receipt_id == graph.upload_receipt_id
        return claim


def _package(
    graph: Graph,
    *,
    price: int | None = 0,
    source_product_id: str | None = None,
) -> CleanedProductPackage:
    product_id = source_product_id or graph.source_product_id
    return CleanedProductPackage(
        source_platform=SourcePlatform.DOUYIN,
        source_product_id=product_id,
        captured_at=datetime.now(UTC),
        source_format_version=1,
        cleaner_version="uu-adapter-v1",
        title="真实零价测试商品" if price == 0 else "测试商品",
        source_url=f"https://example.test/product/{product_id}",
        primary_image_url="https://img.example.test/product.webp",
        merchant_snapshot={"source_id": "merchant-1", "display_name": "测试商家"},
        category_path=("家居", "收纳"),
        current_sale_price_cent=price,
        currency="CNY" if price is not None else None,
        uu_snapshot={
            "productId": graph.source_product_id,
            "skus": [{"skuId": "9000000000000000001"}],
        },
        price_evidence={"state": "available" if price is not None else "unknown"},
    )


def _actor(graph: Graph) -> ActorContext:
    return ActorContext(
        graph.user_id,
        "product collection integration",
        graph.team_id,
        uuid4(),
        "member",
        DataScope.TEAM,
    )


class _Gateway:
    def __init__(self) -> None:
        self.commands = []

    def deliver(self, command):
        self.commands.append(command)
        return GatewayDispatchResult(
            gateway_id="test-gateway",
            gateway_job_id=f"job-{command.external_job_id}",
            external_job_id=command.external_job_id,
            status="pending",
            reused=False,
        )

    def retry(self, *, gateway_job_id):
        raise AssertionError(f"unexpected retry for {gateway_job_id}")

    def cancel(self, *, gateway_job_id):
        raise AssertionError(f"unexpected cancel for {gateway_job_id}")

    def settle(self, settlement):
        raise AssertionError(f"unexpected settlement for {settlement.job_id}")


def _insert_running_cancel_chain(session: Session, graph: Graph, *, product_id: str):
    now = datetime.now(UTC)
    request_id, item_id, dispatch_id, attempt_id = uuid4(), uuid4(), uuid4(), uuid4()
    gateway_job_id = f"job-{dispatch_id}"
    request = CollectionRequest(
        request_id=request_id,
        team_id=graph.team_id,
        requested_by_user_id=graph.user_id,
        submission_key=uuid4(),
        source_kind="manual",
        canonical_request_hash="1" * 64,
        status="running",
        item_count=1,
        cancel_requested_at=now,
        cancel_requested_by_user_id=graph.user_id,
    )
    item = Item(
        item_id=item_id,
        request_id=request_id,
        team_id=graph.team_id,
        platform="douyin",
        source_product_id=product_id,
        collection_mode="auto_gateway",
        state="running",
        attempt_count=1,
    )
    session.add(request)
    session.flush()
    session.add(item)
    session.flush()
    dispatch = Dispatch(
        dispatch_id=dispatch_id,
        item_id=item_id,
        team_id=graph.team_id,
        dispatch_no=1,
        external_job_id=f"pcd_v1_{dispatch_id.hex}",
        canonical_payload_hash="2" * 64,
        gateway_id="test-gateway",
        gateway_job_id=gateway_job_id,
        state="running",
        delivery_attempts=1,
        last_heartbeat_at=now,
    )
    session.add(dispatch)
    session.flush()
    item.current_dispatch_id = dispatch_id
    attempt = CaptureAttempt(
        attempt_id=attempt_id,
        dispatch_id=dispatch_id,
        gateway_id="test-gateway",
        team_id=graph.team_id,
        gateway_device_id=f"device-{attempt_id}",
        gateway_job_id=gateway_job_id,
        capture_batch_id=f"batch-{attempt_id}",
        attempt_no=1,
        ingest_credential_id=uuid4(),
        ingest_credential_version=1,
        ingest_token_key_id="test-key-v1",
        ingest_token_salt="3" * 32,
        ingest_token_hash="4" * 64,
        token_issued_at=now,
        token_expires_at=now + timedelta(minutes=10),
        accept_until=now + timedelta(minutes=15),
        state="running",
        lease_expires_at=now + timedelta(minutes=15),
        last_heartbeat_at=now,
        registered_at=now,
    )
    session.add(attempt)
    session.flush()
    return request_id, item_id, dispatch_id, attempt_id, gateway_job_id


def test_terminal_gateway_failure_reconciles_cancel_intent_idempotently(graph: Graph):
    with Session(graph.engine) as session:
        ids = _insert_running_cancel_chain(
            session,
            graph,
            product_id=str(6_410_000_000_000_000_000 + graph.user_id.int % 100_000),
        )
        request_id, item_id, dispatch_id, attempt_id, gateway_job_id = ids
        assert ProductCollectionDispatchService(session)._reconcile_cancel_result(
            dispatch_id=dispatch_id,
            team_id=graph.team_id,
            gateway_job_id=gateway_job_id,
            status="failed",
        )
    with Session(graph.engine) as session:
        assert not ProductCollectionDispatchService(session)._reconcile_cancel_result(
            dispatch_id=dispatch_id,
            team_id=graph.team_id,
            gateway_job_id=gateway_job_id,
            status="failed",
        )

    with Session(graph.engine) as session:
        request = session.get(CollectionRequest, request_id)
        item = session.get(Item, item_id)
        dispatch = session.get(Dispatch, dispatch_id)
        attempt = session.get(CaptureAttempt, attempt_id)
        assert request.cancel_requested_at is not None
        assert request.cancel_requested_by_user_id == graph.user_id
        assert request.status == "failed" and request.finished_at is not None
        assert item.state == "failed" and item.finished_at is not None
        assert dispatch.state == "execution_failed" and dispatch.finished_at is not None
        assert attempt.state == "failed" and attempt.finished_at is not None
        assert item.last_error_code == "PRODUCT_COLLECTION_GATEWAY_EXECUTION_FAILED"
        assert dispatch.last_error_code == item.last_error_code
        assert attempt.last_error_code == item.last_error_code
def test_stale_cancel_result_does_not_overwrite_new_current_dispatch(graph: Graph):
    with Session(graph.engine) as session:
        ids = _insert_running_cancel_chain(
            session,
            graph,
            product_id=str(6_430_000_000_000_000_000 + graph.user_id.int % 100_000),
        )
        request_id, item_id, old_dispatch_id, _, old_gateway_job_id = ids
        old = session.get(Dispatch, old_dispatch_id)
        item = session.get(Item, item_id)
        now = datetime.now(UTC)
        old.state = "execution_failed"
        old.finished_at = now
        old.last_heartbeat_at = None
        old.last_error_code = "PRODUCT_COLLECTION_GATEWAY_EXECUTION_FAILED"
        old.last_error_stage = "gateway_execution"
        old.last_error_message = "并发终态"
        new_dispatch_id = uuid4()
        replacement = Dispatch(
            dispatch_id=new_dispatch_id,
            item_id=item.item_id,
            team_id=item.team_id,
            dispatch_no=old.dispatch_no + 1,
            external_job_id=f"pcd_v1_{new_dispatch_id.hex}",
            canonical_payload_hash="f" * 64,
            gateway_id=old.gateway_id,
            gateway_job_id=f"job-{new_dispatch_id}",
            state="execution_failed",
            delivery_attempts=0,
            last_error_code="NEWER_DISPATCH_RESULT",
            last_error_stage="gateway_execution",
            last_error_message="较新派发结果",
            finished_at=now,
        )
        session.add(replacement)
        session.flush()
        item.current_dispatch_id = replacement.dispatch_id
        item.state = "failed"
        item.last_error_code = replacement.last_error_code
        item.last_error_stage = replacement.last_error_stage
        item.last_error_message = replacement.last_error_message
        item.finished_at = now
        request = session.get(CollectionRequest, request_id)
        request.status = "failed"
        request.finished_at = now
        session.commit()
        assert not ProductCollectionDispatchService(session)._reconcile_cancel_result(
            dispatch_id=old_dispatch_id,
            team_id=graph.team_id,
            gateway_job_id=old_gateway_job_id,
            status="canceled",
        )

    with Session(graph.engine) as session:
        request = session.get(CollectionRequest, request_id)
        item = session.get(Item, item_id)
        old = session.get(Dispatch, old_dispatch_id)
        replacement = session.get(Dispatch, new_dispatch_id)
        assert request.cancel_requested_at is not None and request.status == "failed"
        assert item.current_dispatch_id == new_dispatch_id and item.state == "failed"
        assert old.state == "execution_failed"
        assert replacement.state == "execution_failed" and replacement.finished_at is not None
        assert replacement.last_error_code == "NEWER_DISPATCH_RESULT"
        assert item.last_error_code == replacement.last_error_code


def _accept_gateway_upload(graph: Graph, *, source_product_id: str) -> AcceptedUpload:
    command = ProductCollectionRequestCreate.model_validate(
        {
            "submission_key": uuid4(),
            "source": {
                "kind": "manual",
                "targets": [
                    {
                        "platform": "douyin",
                        "product_id_or_supported_url": source_product_id,
                    },
                ],
            },
        },
    )
    with Session(graph.engine, expire_on_commit=False) as session:
        request = ProductCollectionHumanService(session).create_request(
            _actor(graph),
            command,
        )
    with Session(graph.engine) as session:
        assert ProductCollectionDispatchService(session).plan_pending(
            gateway_id="test-gateway",
        ) == 1
    gateway = _Gateway()
    with Session(graph.engine) as session:
        assert ProductCollectionDispatchService(session).deliver_once(
            gateway,
            lease_seconds=120,
            max_attempts=3,
            retry_delay_seconds=1,
        )

    with Session(graph.engine) as session:
        item = session.scalar(select(Item).where(Item.request_id == request.request_id))
        dispatch = session.get(Dispatch, item.current_dispatch_id)
        registration = GatewayAttemptRegistrationV1(
            schema_version=1,
            dispatch_id=dispatch.dispatch_id,
            gateway_id="test-gateway",
            external_job_id=dispatch.external_job_id,
            gateway_job_id=dispatch.gateway_job_id,
            device_id="device-integration",
            capture_batch_id=f"batch-{uuid4()}",
            source_platform="douyin",
            source_product_id=source_product_id,
            lease_expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
        item_id = item.item_id
    with Session(graph.engine, expire_on_commit=False) as session:
        control = ProductCollectionIngestService(session).register_attempt(
            registration,
            secret=b"s" * 32,
            key_id="test-key-v1",
            public_base_url="http://127.0.0.1:8101",
            token_ttl_seconds=600,
            accept_grace_seconds=300,
        )

    body = {
        "eventType": "complete",
        "detailBody": {"productId": source_product_id, "title": "integration"},
        "skuBody": {"productId": source_product_id, "skus": []},
        "capturedAt": int(datetime.now(UTC).timestamp() * 1000),
        "taskContext": {
            "jobId": registration.gateway_job_id,
            "captureBatchId": registration.capture_batch_id,
            "jobType": "product",
            "sourcePlatform": "douyin",
            "sourceProductId": source_product_id,
        },
    }
    raw = json.dumps(body).encode()
    with Session(graph.engine, expire_on_commit=False) as session:
        accepted = ProductCollectionIngestService(session).accept_complete_package(
            attempt_id=control.attempt_id,
            credential=control.credential,
            raw_body=raw,
        )
        assert accepted.receipt.status == "received"
    return AcceptedUpload(
        request_id=request.request_id,
        item_id=item_id,
        attempt_id=control.attempt_id,
        receipt_id=accepted.receipt.receipt_id,
        credential=control.credential,
        raw=raw,
        source_product_id=source_product_id,
    )


def test_upload_constraints_reject_terminal_settlement_on_received(graph: Graph):
    with Session(graph.engine) as session:
        with pytest.raises(IntegrityError) as error:
            with session.begin_nested():
                session.execute(
                    update(UploadReceipt)
                    .where(UploadReceipt.upload_receipt_id == graph.upload_receipt_id)
                    .values(gateway_settlement_state="pending"),
                )
                session.flush()
        assert error.value.orig.sqlstate == "23514"


def test_success_is_one_transaction_and_preserves_real_zero(graph: Graph):
    claim = _claim(graph)
    with Session(graph.engine, expire_on_commit=False) as session:
        result = ProductCollectionProcessingService(session).persist(
            claim,
            _package(graph, price=0),
        )
        assert result.applied and result.outcome == "applied"

    with Session(graph.engine) as session:
        upload = session.get(UploadReceipt, graph.upload_receipt_id)
        product = session.get(Product, result.product_id)
        item = session.get(Item, graph.item_id)
        request = session.get(CollectionRequest, graph.request_id)
        attempt = session.get(CaptureAttempt, graph.attempt_id)
        dispatch = session.get(Dispatch, graph.dispatch_id)
        assert upload.state == "persisted"
        assert upload.gateway_settlement_state == "pending"
        assert upload.lease_id is None and upload.processed_at is not None
        assert session.scalar(
            select(func.count())
            .select_from(PersistReceipt)
            .where(PersistReceipt.upload_receipt_id == graph.upload_receipt_id),
        ) == 1
        assert session.scalar(
            select(func.count())
            .select_from(ProductVersion)
            .where(ProductVersion.upload_receipt_id == graph.upload_receipt_id),
        ) == 1
        assert product.current_sale_price_cent == 0
        assert product.adopted_version_id == result.version_id
        assert item.state == "succeeded" and item.library_product_id == product.product_id
        assert request.status == "succeeded" and request.finished_at is not None
        assert attempt.state == "persisted" and dispatch.state == "completed"


def test_processing_failure_keeps_raw_and_has_no_persist_receipt(graph: Graph):
    claim = _claim(graph)
    with Session(graph.engine) as session:
        ProductCollectionProcessingService(session).fail(
            claim,
            error_code="PRODUCT_COLLECTION_CLEANER_INVALID",
            error_stage="cleaner",
            error_message="  invalid   package  ",
        )

    with Session(graph.engine) as session:
        upload = session.get(UploadReceipt, graph.upload_receipt_id)
        assert upload.state == "failed"
        assert upload.gateway_settlement_state == "pending"
        assert upload.raw_payload["detailBody"]["productId"] == graph.source_product_id
        assert upload.last_error_message == "invalid package"
        assert session.scalar(
            select(func.count())
            .select_from(PersistReceipt)
            .where(PersistReceipt.upload_receipt_id == graph.upload_receipt_id),
        ) == 0
        assert session.get(Item, graph.item_id).state == "failed"
        assert session.get(CollectionRequest, graph.request_id).status == "failed"


def test_expired_processing_lease_is_reclaimed_and_fences_old_worker(graph: Graph):
    first = _claim(graph)
    with Session(graph.engine) as session:
        session.execute(
            update(UploadReceipt)
            .where(UploadReceipt.upload_receipt_id == graph.upload_receipt_id)
            .values(lease_expires_at=func.clock_timestamp() - timedelta(seconds=1)),
        )
        session.commit()

    with Session(graph.engine, expire_on_commit=False) as session:
        second = ProductCollectionProcessingService(session).claim(lease_seconds=120)
        assert second is not None
        assert second.upload_receipt_id == first.upload_receipt_id
        assert second.lease_id != first.lease_id

    with Session(graph.engine) as session:
        upload = session.get(UploadReceipt, graph.upload_receipt_id)
        assert upload.state == "processing"
        assert upload.processing_attempts == 2
        assert upload.lease_id == second.lease_id
        with pytest.raises(ProductCollectionLeaseLostError):
            ProductCollectionProcessingService(session).raw_payload(first)

    with Session(graph.engine) as session:
        ProductCollectionProcessingService(session).persist(second, _package(graph))


def test_settlement_is_fenced_and_success_mirrors_attempt(graph: Graph):
    claim = _claim(graph)
    with Session(graph.engine) as session:
        ProductCollectionProcessingService(session).persist(claim, _package(graph))

    with Session(graph.engine, expire_on_commit=False) as session:
        settlement = ProductCollectionSettlementService(session).claim(
            max_attempts=3,
            delivery_timeout_seconds=60,
        )
        assert settlement is not None
        assert settlement.attempt_no == 1
        assert settlement.settlement.status == "succeeded"
        assert settlement.settlement.product_version_id is not None
        assert settlement.settlement.uu_sha256 is not None
    with Session(graph.engine) as session:
        ProductCollectionSettlementService(session).succeed(settlement)

    with Session(graph.engine) as session:
        upload = session.get(UploadReceipt, graph.upload_receipt_id)
        attempt = session.get(CaptureAttempt, graph.attempt_id)
        assert upload.gateway_settlement_state == "settled"
        assert upload.settled_at is not None
        assert upload.next_attempt_at is None
        assert upload.settlement_error_code is None
        assert attempt.settled_at == upload.settled_at


def test_settlement_retry_budget_stops_with_error_retained(graph: Graph):
    claim = _claim(graph)
    with Session(graph.engine) as session:
        ProductCollectionProcessingService(session).fail(
            claim,
            error_code="PRODUCT_COLLECTION_CLEANER_INVALID",
            error_stage="cleaner",
            error_message="invalid package",
        )

    with Session(graph.engine, expire_on_commit=False) as session:
        first = ProductCollectionSettlementService(session).claim(
            max_attempts=2,
            delivery_timeout_seconds=60,
        )
        assert first is not None
    with Session(graph.engine) as session:
        assert ProductCollectionSettlementService(session).fail(
            first,
            error_code="GATEWAY_TIMEOUT",
            error_message="gateway timeout",
            max_attempts=2,
            retry_delay_seconds=60,
            at=datetime.now(UTC) - timedelta(minutes=2),
        )

    with Session(graph.engine, expire_on_commit=False) as session:
        second = ProductCollectionSettlementService(session).claim(
            max_attempts=2,
            delivery_timeout_seconds=60,
        )
        assert second is not None and second.attempt_no == 2
    with Session(graph.engine) as session:
        assert not ProductCollectionSettlementService(session).fail(
            second,
            error_code="GATEWAY_REJECTED",
            error_message="gateway rejected terminal callback",
            max_attempts=2,
            retry_delay_seconds=60,
        )

    with Session(graph.engine) as session:
        upload = session.get(UploadReceipt, graph.upload_receipt_id)
        assert upload.gateway_settlement_state == "failed"
        assert upload.gateway_settlement_attempts == 2
        assert upload.next_attempt_at is None
        assert upload.settlement_error_code == "GATEWAY_REJECTED"
        assert ProductCollectionSettlementService(session).claim(
            max_attempts=2,
            delivery_timeout_seconds=60,
        ) is None


def test_two_processes_cannot_claim_same_settlement(graph: Graph):
    claim = _claim(graph)
    with Session(graph.engine) as session:
        ProductCollectionProcessingService(session).persist(claim, _package(graph))

    barrier = Barrier(2)

    def race(_index: int):
        with Session(graph.engine, expire_on_commit=False) as session:
            session.execute(text("SET LOCAL lock_timeout = '5s'"))
            session.execute(text("SET LOCAL statement_timeout = '10s'"))
            barrier.wait(timeout=10)
            return ProductCollectionSettlementService(session).claim(
                max_attempts=3,
                delivery_timeout_seconds=60,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(race, range(2)))
    assert sum(result is not None for result in results) == 1
    only = next(result for result in results if result is not None)
    assert only.upload_receipt_id == graph.upload_receipt_id


def test_human_submission_is_normalized_idempotent_and_conflict_safe(graph: Graph):
    submission_key = uuid4()
    product_id = str(7_770_000_000_000_000_000 + graph.user_id.int % 100_000)
    command = ProductCollectionRequestCreate.model_validate(
        {
            "submission_key": submission_key,
            "source": {
                "kind": "manual",
                "targets": [
                    {"platform": "douyin", "product_id_or_supported_url": product_id},
                    {"platform": "douyin", "product_id_or_supported_url": product_id},
                ],
            },
        },
    )
    with Session(graph.engine, expire_on_commit=False) as session:
        first = ProductCollectionHumanService(session).create_request(_actor(graph), command)
        assert first.item_count == 1 and not first.reused
    with Session(graph.engine, expire_on_commit=False) as session:
        replay = ProductCollectionHumanService(session).create_request(_actor(graph), command)
        assert replay.request_id == first.request_id and replay.reused
        assert session.scalar(
            select(func.count()).select_from(Item).where(Item.request_id == first.request_id),
        ) == 1

    conflict = ProductCollectionRequestCreate.model_validate(
        {
            "submission_key": submission_key,
            "source": {
                "kind": "manual",
                "targets": [
                    {
                        "platform": "douyin",
                        "product_id_or_supported_url": str(int(product_id) + 1),
                    },
                ],
            },
        },
    )
    with Session(graph.engine) as session:
        with pytest.raises(ProductCollectionSubmissionConflictError):
            ProductCollectionHumanService(session).create_request(_actor(graph), conflict)

    other_team_super = ActorContext(
        graph.user_id,
        "cross-team super",
        uuid4(),
        None,
        "super_account",
        DataScope.ALL,
        True,
    )
    with Session(graph.engine) as session:
        with pytest.raises(ProductCollectionRequestNotFoundError):
            ProductCollectionHumanService(session).get_request(
                other_team_super,
                first.request_id,
            )


def test_candidate_submission_reuses_existing_visibility_and_shop_authorization(graph: Graph):
    now = datetime.now(UTC)
    shop_id, candidate_id, observation_id = uuid4(), uuid4(), uuid4()
    product_id = str(7_880_000_000_000_000_000 + graph.user_id.int % 100_000)
    with Session(graph.engine) as session:
        session.add(
            Shop(
                shop_id=shop_id,
                display_name="product-collection-visible-shop",
                platform=ShopPlatform.DOUYIN,
                owner_user_id=graph.user_id,
            ),
        )
        session.flush()
        session.add(TeamShopAccess(team_id=graph.team_id, shop_id=shop_id))
        session.add(
            SelectionCandidate(
                candidate_id=candidate_id,
                team_id=graph.team_id,
                created_by_user_id=graph.user_id,
                platform="douyin",
                platform_product_id=product_id,
            ),
        )
        session.flush()
        session.add(
            SelectionObservation(
                observation_id=observation_id,
                candidate_id=candidate_id,
                request_shop_id=shop_id,
                source_scope_hash="f" * 64,
                source_context={"version": 1},
                period_begin=date(2026, 10, 1),
                period_end=date(2026, 10, 7),
                merchant_snapshot=[],
                video_metric_ranges={},
                first_seen_at=now,
                checked_at=now,
                metrics_retrieved_at=now,
                last_attempt_at=now,
                last_successful_request_started_at=now,
                basic_info_version=0,
            ),
        )
        session.commit()

    command = ProductCollectionRequestCreate.model_validate(
        {
            "submission_key": uuid4(),
            "source": {
                "kind": "selection_candidates",
                "candidate_ids": [candidate_id],
            },
        },
    )
    with Session(graph.engine, expire_on_commit=False) as session:
        receipt = ProductCollectionHumanService(session).create_request(
            _actor(graph),
            command,
        )
        item = session.scalar(select(Item).where(Item.request_id == receipt.request_id))
        assert item.candidate_id == candidate_id
        assert item.source_product_id == product_id

    with Session(graph.engine) as session:
        session.execute(
            delete(TeamShopAccess).where(
                TeamShopAccess.team_id == graph.team_id,
                TeamShopAccess.shop_id == shop_id,
            ),
        )
        session.commit()
    blocked = command.model_copy(update={"submission_key": uuid4()})
    with Session(graph.engine) as session:
        from app.modules.product_collection.exceptions import (
            ProductCollectionCandidateNotFoundError,
        )

        with pytest.raises(ProductCollectionCandidateNotFoundError):
            ProductCollectionHumanService(session).create_request(_actor(graph), blocked)


def test_request_to_gateway_attempt_and_raw_upload_is_durable(graph: Graph):
    product_id = str(6_660_000_000_000_000_000 + graph.user_id.int % 100_000)
    command = ProductCollectionRequestCreate.model_validate(
        {
            "submission_key": uuid4(),
            "source": {
                "kind": "manual",
                "targets": [
                    {"platform": "douyin", "product_id_or_supported_url": product_id},
                ],
            },
        },
    )
    with Session(graph.engine, expire_on_commit=False) as session:
        request = ProductCollectionHumanService(session).create_request(_actor(graph), command)

    with Session(graph.engine) as session:
        assert ProductCollectionDispatchService(session).plan_pending(
            gateway_id="test-gateway",
        ) == 1
    gateway = _Gateway()
    with Session(graph.engine) as session:
        assert ProductCollectionDispatchService(session).deliver_once(
            gateway,
            lease_seconds=120,
            max_attempts=3,
            retry_delay_seconds=1,
        )
    assert len(gateway.commands) == 1

    with Session(graph.engine) as session:
        item = session.scalar(select(Item).where(Item.request_id == request.request_id))
        dispatch = session.get(Dispatch, item.current_dispatch_id)
        assert item.state == "dispatched"
        assert dispatch.state == "dispatched"
        dispatch_id = dispatch.dispatch_id
        external_job_id = dispatch.external_job_id
        gateway_job_id = dispatch.gateway_job_id

    registration = GatewayAttemptRegistrationV1(
        schema_version=1,
        dispatch_id=dispatch_id,
        gateway_id="test-gateway",
        external_job_id=external_job_id,
        gateway_job_id=gateway_job_id,
        device_id="device-integration",
        capture_batch_id=f"batch-{uuid4()}",
        source_platform="douyin",
        source_product_id=product_id,
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    with Session(graph.engine, expire_on_commit=False) as session:
        control = ProductCollectionIngestService(session).register_attempt(
            registration,
            secret=b"s" * 32,
            key_id="test-key-v1",
            public_base_url="http://127.0.0.1:8101",
            token_ttl_seconds=600,
            accept_grace_seconds=300,
        )

    body = {
        "eventType": "complete",
        "detailBody": {"productId": product_id, "title": "integration"},
        "skuBody": {"productId": product_id, "skus": []},
        "capturedAt": int(datetime.now(UTC).timestamp() * 1000),
        "taskContext": {
            "jobId": gateway_job_id,
            "captureBatchId": registration.capture_batch_id,
            "jobType": "product",
            "sourcePlatform": "douyin",
            "sourceProductId": product_id,
        },
    }
    raw = json.dumps(body).encode()
    upload_barrier = Barrier(2)

    def upload_replay(_index: int):
        with Session(graph.engine, expire_on_commit=False) as session:
            upload_barrier.wait(timeout=10)
            return ProductCollectionIngestService(session).accept_complete_package(
                attempt_id=control.attempt_id,
                credential=control.credential,
                raw_body=raw,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        accepted = list(pool.map(upload_replay, range(2)))
    assert {item.receipt.status for item in accepted} == {"received", "duplicate"}
    assert len({item.receipt.receipt_id for item in accepted}) == 1
    first = next(item.receipt for item in accepted if item.receipt.status == "received")

    changed = {**body, "detailBody": {**body["detailBody"], "title": "changed"}}
    with Session(graph.engine) as session:
        with pytest.raises(ProductCollectionUploadConflictError):
            ProductCollectionIngestService(session).accept_complete_package(
                attempt_id=control.attempt_id,
                credential=control.credential,
                raw_body=json.dumps(changed).encode(),
            )

    with Session(graph.engine) as session:
        upload = session.get(UploadReceipt, first.receipt_id)
        assert upload.state == "received"
        assert upload.raw_payload["detailBody"]["productId"] == product_id
        assert session.get(Item, item.item_id).state == "received"


def test_terminal_upload_replay_is_stable_and_still_authenticates(
    graph: Graph,
    monkeypatch: pytest.MonkeyPatch,
):
    # Clear the fixture's pre-existing inbox row so subsequent claims target
    # the packages accepted through the real ingest service below.
    with Session(graph.engine) as session:
        ProductCollectionProcessingService(session).persist(_claim(graph), _package(graph))

    persisted = _accept_gateway_upload(
        graph,
        source_product_id=str(6_640_000_000_000_000_000 + graph.user_id.int % 100_000),
    )
    with Session(graph.engine, expire_on_commit=False) as session:
        claim = ProductCollectionProcessingService(session).claim(lease_seconds=120)
        assert claim is not None and claim.upload_receipt_id == persisted.receipt_id
    with Session(graph.engine) as session:
        ProductCollectionProcessingService(session).persist(
            claim,
            _package(graph, source_product_id=persisted.source_product_id),
        )

    with Session(graph.engine) as session:
        duplicate = ProductCollectionIngestService(session).accept_complete_package(
            attempt_id=persisted.attempt_id,
            credential=persisted.credential,
            raw_body=persisted.raw,
        )
        assert duplicate.receipt.status == "duplicate"
        assert duplicate.receipt.receipt_id == persisted.receipt_id

    changed = json.loads(persisted.raw)
    changed["detailBody"]["title"] = "different-content"
    with Session(graph.engine) as session:
        with pytest.raises(ProductCollectionUploadConflictError):
            ProductCollectionIngestService(session).accept_complete_package(
                attempt_id=persisted.attempt_id,
                credential=persisted.credential,
                raw_body=json.dumps(changed).encode(),
            )

    def unexpected_parse(_raw: bytes):
        raise AssertionError("invalid credentials must be rejected before parsing")

    with monkeypatch.context() as scoped:
        scoped.setattr(
            "app.modules.product_collection.ingest_service.parse_complete_package",
            unexpected_parse,
        )
        with Session(graph.engine) as session:
            with pytest.raises(ProductCollectionIngestCredentialError):
                ProductCollectionIngestService(session).accept_complete_package(
                    attempt_id=persisted.attempt_id,
                    credential="wrong-credential",
                    raw_body=b"not-json",
                )

    with Session(graph.engine) as session:
        attempt = session.get(CaptureAttempt, persisted.attempt_id)
        attempt.token_expires_at = attempt.token_issued_at
        session.commit()
    with Session(graph.engine) as session:
        with pytest.raises(ProductCollectionIngestCredentialError):
            ProductCollectionIngestService(session).accept_complete_package(
                attempt_id=persisted.attempt_id,
                credential=persisted.credential,
                raw_body=persisted.raw,
            )

    failed = _accept_gateway_upload(
        graph,
        source_product_id=str(6_630_000_000_000_000_000 + graph.user_id.int % 100_000),
    )
    with Session(graph.engine, expire_on_commit=False) as session:
        failed_claim = ProductCollectionProcessingService(session).claim(lease_seconds=120)
        assert failed_claim is not None
        assert failed_claim.upload_receipt_id == failed.receipt_id
    with Session(graph.engine) as session:
        ProductCollectionProcessingService(session).fail(
            failed_claim,
            error_code="PRODUCT_COLLECTION_CLEANER_INVALID",
            error_stage="cleaner",
            error_message="invalid package",
        )
    with Session(graph.engine) as session:
        duplicate = ProductCollectionIngestService(session).accept_complete_package(
            attempt_id=failed.attempt_id,
            credential=failed.credential,
            raw_body=failed.raw,
        )
        assert duplicate.receipt.status == "duplicate"
        assert duplicate.receipt.receipt_id == failed.receipt_id


def test_expired_final_delivery_claim_is_closed_after_restart(graph: Graph):
    product_id = str(6_600_000_000_000_000_000 + graph.user_id.int % 100_000)
    command = ProductCollectionRequestCreate.model_validate(
        {
            "submission_key": uuid4(),
            "source": {
                "kind": "manual",
                "targets": [
                    {"platform": "douyin", "product_id_or_supported_url": product_id},
                ],
            },
        },
    )
    with Session(graph.engine, expire_on_commit=False) as session:
        request = ProductCollectionHumanService(session).create_request(
            _actor(graph),
            command,
        )
    with Session(graph.engine) as session:
        assert ProductCollectionDispatchService(session).plan_pending(
            gateway_id="test-gateway",
        ) == 1

    with Session(graph.engine, expire_on_commit=False) as session:
        claim = ProductCollectionDispatchService(session).claim(
            lease_seconds=120,
            max_attempts=1,
        )
        assert claim is not None and claim.attempt_no == 1

    with Session(graph.engine) as session:
        session.execute(
            update(Dispatch)
            .where(Dispatch.dispatch_id == claim.dispatch_id)
            .values(lease_expires_at=func.clock_timestamp() - timedelta(seconds=1)),
        )
        session.commit()

    with Session(graph.engine) as session:
        assert ProductCollectionDispatchService(session).claim(
            lease_seconds=120,
            max_attempts=1,
        ) is None

    with Session(graph.engine) as session:
        dispatch = session.get(Dispatch, claim.dispatch_id)
        item = session.scalar(select(Item).where(Item.request_id == request.request_id))
        persisted_request = session.get(CollectionRequest, request.request_id)
        assert dispatch.state == "delivery_failed"
        assert dispatch.delivery_attempts == 1
        assert dispatch.lease_id is None and dispatch.lease_expires_at is None
        assert dispatch.last_error_code == (
            "PRODUCT_COLLECTION_GATEWAY_DELIVERY_INTERRUPTED"
        )
        assert item.state == "failed"
        assert item.last_error_code == dispatch.last_error_code
        assert persisted_request.status == "failed"


def test_finite_retry_reuses_dispatch_and_recapture_creates_new_identity(graph: Graph):
    product_id = str(6_550_000_000_000_000_000 + graph.user_id.int % 100_000)
    command = ProductCollectionRequestCreate.model_validate(
        {
            "submission_key": uuid4(),
            "source": {
                "kind": "manual",
                "targets": [
                    {"platform": "douyin", "product_id_or_supported_url": product_id},
                ],
            },
        },
    )
    with Session(graph.engine, expire_on_commit=False) as session:
        receipt = ProductCollectionHumanService(session).create_request(_actor(graph), command)
    with Session(graph.engine) as session:
        ProductCollectionDispatchService(session).plan_pending(gateway_id="test-gateway")
        item = session.scalar(select(Item).where(Item.request_id == receipt.request_id))
        item_id = item.item_id
        original_dispatch_id = item.current_dispatch_id
        dispatch = session.get(Dispatch, original_dispatch_id)
        dispatch.state = "delivery_failed"
        dispatch.delivery_attempts = 1
        dispatch.finished_at = datetime.now(UTC)
        item.state = "failed"
        item.finished_at = dispatch.finished_at
        request = session.get(CollectionRequest, receipt.request_id)
        request.status = "failed"
        request.finished_at = dispatch.finished_at
        session.commit()

    with Session(graph.engine, expire_on_commit=False) as session:
        ProductCollectionHumanService(session).retry_item(
            _actor(graph),
            item_id,
            max_delivery_attempts=3,
            max_capture_attempts=3,
        )
    with Session(graph.engine) as session:
        item = session.get(Item, item_id)
        dispatch = session.get(Dispatch, original_dispatch_id)
        assert item.current_dispatch_id == original_dispatch_id
        assert dispatch.state == "pending_delivery"
        assert dispatch.delivery_attempts == 1
        retry_command = command_from_dispatch(dispatch, item)
        assert retry_command.canonical_payload_hash == dispatch.canonical_payload_hash
        assert retry_command.external_job_id == dispatch.external_job_id
        assert retry_command.recapture is False
        dispatch.state = "delivery_failed"
        dispatch.delivery_attempts = 3
        dispatch.finished_at = datetime.now(UTC)
        item.state = "failed"
        item.finished_at = dispatch.finished_at
        session.commit()

    with Session(graph.engine, expire_on_commit=False) as session:
        ProductCollectionHumanService(session).recapture_item(
            _actor(graph),
            item_id,
            gateway_id="test-gateway",
        )
    with Session(graph.engine) as session:
        item = session.get(Item, item_id)
        replacement = session.get(Dispatch, item.current_dispatch_id)
        original = session.get(Dispatch, original_dispatch_id)
        assert replacement.dispatch_id != original.dispatch_id
        assert replacement.dispatch_no == original.dispatch_no + 1
        assert replacement.external_job_id != original.external_job_id
        assert original.state == "delivery_failed"
        assert original.delivery_attempts == 3
        recapture_command = command_from_dispatch(replacement, item)
        assert recapture_command.canonical_payload_hash == replacement.canonical_payload_hash
        assert recapture_command.external_job_id == replacement.external_job_id
        assert recapture_command.recapture is True
