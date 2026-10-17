"""Registered Feature PostgreSQL; synthetic people, Sessions and platform I/O only."""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from threading import Lock, local
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, make_url, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_database_engine
from app.core.security import SecretCipher
from app.main import create_app
from app.modules.access.models import Team, TeamMembership, TeamModuleAccess, TeamShopAccess
from app.modules.access.service import ActorContextService
from app.modules.operating_dashboard.api import get_operating_dashboard_actor, get_operating_dashboard_service
from app.modules.operating_dashboard.executor import OperatingDataCollectionExecutor
from app.modules.operating_dashboard.models import OperatingDataCollectionItem, OperatingDataCollectionJob, ShopOperatingDailyMetric
from app.modules.operating_dashboard.service import OperatingDashboardService
from app.modules.sessions.auth_context import ShopSessionAccessor, StoredSessionCookie
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.health_service import ShopSessionHealthService
from app.modules.sessions.models import ShopSession
from app.modules.sessions.service import ShopSessionService
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.users.models import User
from app.platforms.douyin.api_client import DouyinApiResponse
from app.platforms.douyin.operating_data import DouyinOperatingDataConnector
from app.platforms.douyin import operating_data_executor as collector_module
from app.platforms.exceptions import PlatformRequestFailedError, PlatformRequestTimeoutError
from app.platforms.schemas import PlatformShopIdentity

pytestmark = pytest.mark.integration
DATABASE = "control_center_feat_product_selection"
ROLE = "control_center_dev_user"


def _foundation_digest(connection):
    # Server-side hashes avoid exporting unrelated existing fixture contents.
    return {
        table: tuple(connection.execute(text(
            f"SELECT count(*), md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY t.{key})::text, '')) FROM {table} t"
        )).one())
        for table, key in (("users", "user_id"), ("teams", "team_id"), ("shops", "shop_id"))
    }


@pytest.fixture
def recovery_engine():
    settings = get_settings()
    assert settings.database_url is not None, "An explicitly registered Feature connection is required"
    url = make_url(str(settings.database_url))
    # Guard before obtaining a connection; never accept a prefix or a shared DB.
    assert url.drivername.startswith("postgresql")
    assert (url.database, url.username, url.host, url.port) == (DATABASE, ROLE, "127.0.0.1", 35433)
    assert not any((
        settings.operating_dashboard_collection_execution_enabled,
        settings.operating_dashboard_daily_collection_enabled,
        settings.product_selection_execution_enabled, settings.product_selection_schedule_enabled,
    )), "All automatic execution switches must remain false"
    engine = get_database_engine()
    with engine.connect() as connection:
        assert tuple(connection.execute(text("SELECT current_database(), current_user")).one()) == (DATABASE, ROLE)
        assert connection.scalars(text("SELECT version_num FROM alembic_version")).all() == ["20261015_0046"]
        before = _foundation_digest(connection)
    yield engine
    with engine.connect() as connection:
        assert _foundation_digest(connection) == before, "Existing users/teams/shops must be byte-preserved"


@pytest.fixture
def recovery_case(recovery_engine):
    now = datetime.now(UTC)
    ids = {name: uuid4() for name in ("user", "team", "outsider", "other_team", "shop1", "shop2")}
    cipher = SecretCipher(Fernet.generate_key().decode())
    originals = []
    with Session(recovery_engine) as session:
        session.add_all([
            User(user_id=ids["user"], display_name="stage-2a1 operating recovery"),
            User(user_id=ids["outsider"], display_name="stage-2a1 operating recovery outsider"),
            Team(team_id=ids["team"], name=f"stage-2a1 recovery {ids['team']}"),
            Team(team_id=ids["other_team"], name=f"stage-2a1 recovery {ids['other_team']}"),
        ])
        session.flush()
        for user, team in (("user", "team"), ("outsider", "other_team")):
            session.add_all([
                TeamMembership(user_id=ids[user], team_id=ids[team], enabled=True),
                TeamModuleAccess(team_id=ids[team], module_code="shop"),
            ])
        for shop_key, days in (("shop1", 2), ("shop2", 6)):
            shop_id = ids[shop_key]
            platform_id = f"synthetic-recovery-{shop_id}"
            session.add(Shop(shop_id=shop_id, display_name=f"stage-2a1 recovery {shop_key}",
                             platform=ShopPlatform.DOUYIN, platform_shop_id=platform_id, enabled=True))
            session.flush()
            session.add(TeamShopAccess(team_id=ids["team"], shop_id=shop_id))
            payload = json.dumps({
                "schema": "management-login.session.v1", "platform": "douyin",
                "identity": {"platform": "douyin", "platformShopId": platform_id, "shopDisplayName": "synthetic fixture"},
                "cookies": [{"name": "sessionid", "value": "synthetic-only", "domain": ".jinritemai.com", "path": "/"}],
            }).encode()
            session.add(ShopSession(shop_id=shop_id, version=3, status=ShopSessionStatus.VALID,
                                    captured_at=now - timedelta(hours=3), validated_at=now - timedelta(minutes=34),
                                    payload_encrypted=cipher.encrypt_bytes(payload)))
            for offset in range(days):
                business_date = date(2026, 10, 10) + timedelta(days=offset)
                job = OperatingDataCollectionJob(kind="daily", status="partial_failed",
                    requested_start_date=business_date, requested_end_date=business_date)
                session.add(job); session.flush()
                item = OperatingDataCollectionItem(collection_job_id=job.collection_job_id,
                    shop_id=shop_id, business_date=business_date, status="failed", retryable=True,
                    attempt_count=3, failure_code="SHOP_SESSION_VALIDATION_FAILED", failure_stage="session_preparation",
                    finished_at=now - timedelta(days=1), updated_at=now - timedelta(days=1))
                session.add(item); session.flush()
                originals.append((job.collection_job_id, item.collection_item_id, shop_id, business_date))
            # Other dates are confirmed zero, not gaps; keep the normal range check bounded.
            if shop_key == "shop1":
                for offset in range(2, 6):
                    OperatingDashboardService(session).repository.upsert_daily_metric(
                        shop_id=shop_id, business_date=date(2026, 10, 10) + timedelta(days=offset),
                        source_code="douyin_compass_core_index_v3", metric_contract="douyin_compass_daily_v2_refund_orders",
                        turnover_cents=0, order_count=0, refund_order_count=0, refund_order_status="available", collected_at=now,
                    )
        session.commit()
    settings = get_settings().model_copy(update={"operating_dashboard_collection_execution_enabled": True})
    case = dict(engine=recovery_engine, ids=ids, originals=originals, cipher=cipher, settings=settings, now=now)
    try:
        yield case
    finally:
        # Only this fixture's stable IDs; no migration, truncate or global deletion.
        shop_ids = (ids["shop1"], ids["shop2"])
        with Session(recovery_engine) as session:
            job_ids = session.scalars(select(OperatingDataCollectionItem.collection_job_id).where(
                OperatingDataCollectionItem.shop_id.in_(shop_ids))).all()
            for model in (OperatingDataCollectionItem, ShopOperatingDailyMetric, ShopSession, TeamShopAccess):
                session.execute(delete(model).where(model.shop_id.in_(shop_ids)))
            session.execute(delete(OperatingDataCollectionJob).where(OperatingDataCollectionJob.collection_job_id.in_(job_ids)))
            session.execute(delete(Shop).where(Shop.shop_id.in_(shop_ids)))
            session.execute(delete(TeamMembership).where(TeamMembership.user_id.in_((ids["user"], ids["outsider"]))))
            session.execute(delete(TeamModuleAccess).where(TeamModuleAccess.team_id.in_((ids["team"], ids["other_team"]))))
            session.execute(delete(Team).where(Team.team_id.in_((ids["team"], ids["other_team"]))))
            session.execute(delete(User).where(User.user_id.in_((ids["user"], ids["outsider"]))))
            session.commit()


def _api(case, method, path, *, body=None, outsider=False):
    """Formal ASGI API/Service/SQL; the authenticated person is synthetic."""
    app = create_app()
    def actor():
        with Session(case["engine"]) as session:
            return ActorContextService(session).resolve(
                user_id=case["ids"]["outsider" if outsider else "user"],
                requested_team_id=case["ids"]["other_team" if outsider else "team"],
            )
    def service():
        with Session(case["engine"]) as session:
            yield OperatingDashboardService(session, settings=case["settings"])
    app.dependency_overrides[get_operating_dashboard_actor] = actor
    app.dependency_overrides[get_operating_dashboard_service] = service
    async def request():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path, json=body)
    return asyncio.run(request())


def _retry(case, original, *, deferred=True, outsider=False):
    body = {"item_ids": [str(original[1])], "session_recovery_version": 3}
    if deferred:
        body["revalidate_current_session"] = True
    return _api(case, "POST", f"/api/v1/operating-dashboard/collections/{original[0]}/retry", body=body, outsider=outsider)


def _read(case, *, outsider=False):
    return _api(case, "GET", "/api/v1/operating-dashboard?start_date=2026-10-10&end_date=2026-10-15", outsider=outsider)


class SyntheticPlatform:
    def __init__(self, case, *, reject_identity=False, cookie_version_conflict=False):
        self.case, self.reject_identity = case, reject_identity
        self.cookie_version_conflict = cookie_version_conflict
        self.identity_calls = self.metric_calls = 0
        self.observations = []
        self.lock = Lock()
        self.local = local()

    def install(self, monkeypatch):
        platform = self

        @contextmanager
        def owned_session():
            with Session(self.case["engine"]) as session:
                self.local.session = session
                yield session

        def identity_connectors():
            session = self.local.session
            class Identity:
                def fetch_shop_identity(self, shop_id, context):
                    platform.observations.append(("identity_transaction", session.in_transaction()))
                    assert not session.in_transaction(), "Identity I/O must be outside the claim/read transaction"
                    with platform.lock:
                        platform.identity_calls += 1
                    if platform.reject_identity:
                        raise PlatformRequestFailedError()
                    updates = ()
                    if platform.cookie_version_conflict:
                        with Session(platform.case["engine"]) as other:
                            stored = other.scalar(select(ShopSession).where(ShopSession.shop_id == shop_id))
                            stored.version += 1
                            other.commit()
                        updates = (StoredSessionCookie(name="sessionid", value="synthetic-rotation", domain=".jinritemai.com", path="/"),)
                    return PlatformShopIdentity(platform_shop_id=f"synthetic-recovery-{shop_id}", shop_display_name="synthetic fixture", cookie_updates=updates)
            return {ShopPlatform.DOUYIN: Identity()}

        def metrics_connector():
            session = self.local.session
            class Client:
                def request_json(self, endpoint, context, *, query):
                    platform.observations.append(("metrics_transaction", session.in_transaction()))
                    assert not session.in_transaction(), "Metrics I/O must be outside the claim/read transaction"
                    with platform.lock:
                        platform.metric_calls += 1
                    current = platform.local.request
                    assert context.shop_id == current.shop_id
                    assert query["begin_date"] == query["end_date"] == current.statistic_date.strftime("%Y/%m/%d 00:00:00")
                    def metric(value):
                        return {"index_value": {"value": {"value": value}}}
                    return DouyinApiResponse(payload={"st": 0, "data": {"module_data": {"homepage_core_index": {
                        "compass_general_multi_index_card_value": {"data": [{
                            "income_amt": metric(0), "pay_cnt": metric(0), "refund_order_cnt": metric(3),
                        }]}
                    }}}}, cookie_updates=(), signature_duration_ms=0, platform_duration_ms=0)
            return DouyinOperatingDataConnector(api_client=Client())

        # Exercise the production builder, replacing only its protected key,
        # registered Session factory and external adapters. No real HTTP exists.
        monkeypatch.setattr(collector_module, "get_session_factory", lambda: owned_session)
        monkeypatch.setattr(collector_module, "get_secret_cipher", lambda: self.case["cipher"])
        monkeypatch.setattr(collector_module, "create_platform_connectors", identity_connectors)
        monkeypatch.setattr(collector_module, "DouyinOperatingDataConnector", metrics_connector)

    def collect(self, request):
        self.local.request = request
        return collector_module.collect_douyin_operating_data_once(request, settings=self.case["settings"])

    def executor(self):
        return OperatingDataCollectionExecutor(session_factory=lambda: Session(self.case["engine"]),
            collector=self.collect, settings=self.case["settings"])


def test_eight_exhausted_items_recover_through_api_queue_health_and_persisted_read(recovery_case, monkeypatch):
    case = recovery_case
    before = _read(case)
    assert before.status_code == 200
    hints = [row["session_recovery"] for row in before.json()["coverage"]["missing_samples"] if row["session_recovery"]]
    assert len(hints) == 8 and all(hint["requires_validation"] for hint in hints)
    platform = SyntheticPlatform(case)
    platform.install(monkeypatch)
    first = case["originals"][0]
    assert _retry(case, first, deferred=False).status_code == 409
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda _: _retry(case, first), range(2)))
    assert [receipt.status_code for receipt in receipts] == [202, 202]
    job_id = UUID(receipts[0].json()["collection_job_id"])
    assert receipts[1].json()["collection_job_id"] == str(job_id)
    assert platform.identity_calls == platform.metric_calls == 0  # HTTP only enqueues.
    with ThreadPoolExecutor(max_workers=2) as pool:
        processed = list(pool.map(lambda _: platform.executor().execute_available(collection_job_id=job_id), range(2)))
    assert sorted(processed) == [0, 1]
    assert platform.identity_calls == platform.metric_calls == 1, platform.observations
    current_read = _read(case).json()
    steps = [{
        "original_job_id": str(first[0]), "original_item_id": str(first[1]),
        "request": {"item_ids": [str(first[1])], "session_recovery_version": 3, "revalidate_current_session": True},
        "accepted": receipts[0].json(),
        "finished": _api(case, "GET", f"/api/v1/operating-dashboard/collections/{job_id}").json(),
        "after": current_read,
    }]
    for original in case["originals"][1:]:
        hint = next(row["session_recovery"] for row in current_read["coverage"]["missing_samples"]
                    if row["session_recovery"] and row["session_recovery"]["collection_item_id"] == str(original[1]))
        receipt = _retry(case, original, deferred=hint["requires_validation"])
        assert receipt.status_code == 202
        recovered_job_id = receipt.json()["collection_job_id"]
        assert platform.executor().execute_available(collection_job_id=UUID(recovered_job_id)) == 1
        current_read = _read(case).json()
        body = {"item_ids": [str(original[1])], "session_recovery_version": 3}
        if hint["requires_validation"]:
            body["revalidate_current_session"] = True
        steps.append({
            "original_job_id": str(original[0]), "original_item_id": str(original[1]), "request": body,
            "accepted": receipt.json(),
            "finished": _api(case, "GET", f"/api/v1/operating-dashboard/collections/{recovered_job_id}").json(),
            "after": current_read,
        })
    after = _read(case)
    assert after.status_code == 200
    assert after.json()["coverage"]["collected_shop_days"] == after.json()["coverage"]["total_shop_days"] == 12
    assert after.json()["summary"]["turnover_cents"] == 0
    assert after.json()["summary"]["order_count"] == 0
    assert after.json()["summary"]["refund_order_count"] == 24
    assert after.json()["summary"]["refund_order_coverage_complete"] is True
    assert platform.identity_calls == 2 and platform.metric_calls == 8
    with Session(case["engine"]) as session:
        for _, item_id, shop_id, day in case["originals"]:
            original = session.get(OperatingDataCollectionItem, item_id)
            assert original.status == "failed" and original.attempt_count == 3
            metric = session.scalar(select(ShopOperatingDailyMetric).where(
                ShopOperatingDailyMetric.shop_id == shop_id, ShopOperatingDailyMetric.business_date == day))
            assert (metric.turnover_cents, metric.order_count, metric.refund_order_count) == (0, 0, 3)
        count = session.scalar(select(func.count()).select_from(OperatingDataCollectionItem).where(
            OperatingDataCollectionItem.shop_id.in_((case["ids"]["shop1"], case["ids"]["shop2"]))))
        assert count == 16
    assert _retry(case, first).json()["collection_job_id"] == str(job_id)
    body = {"start_date": "2026-10-10", "end_date": "2026-10-15"}
    for _ in range(2):
        response = _api(case, "POST", "/api/v1/operating-dashboard/collections", body=body)
        assert response.status_code == 200 and response.json()["state"] == "up_to_date"
        assert response.json()["collection_job"] is None
    assert (platform.identity_calls, platform.metric_calls) == (2, 8)
    final_job = _api(case, "GET", f"/api/v1/operating-dashboard/collections/{job_id}").json()
    evidence = Path(__file__).resolve().parents[3] / ".codex" / "operating-session-recovery-v1-20261017"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "feature-api-proof.json").write_text(json.dumps({
        "kind": "FEATURE_POSTGRESQL_WITH_SYNTHETIC_PLATFORM_NOT_PRODUCTION",
        "authentication": "synthetic person resolved by real ActorContextService; no platform login",
        "database": DATABASE, "role": ROLE, "migration": "20261015_0046",
        "before": before.json(), "accepted": receipts[0].json(), "finished": final_job,
        "after": after.json(), "identity_adapter_calls": 2, "metrics_adapter_calls": 8,
        "steps": steps,
        "original_failures_preserved": 8, "ordinary_complete_updates_created_jobs": 0,
        "io_transaction_states": platform.observations,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def test_recovery_validation_failure_is_terminal_and_preserves_original_data(recovery_case, monkeypatch):
    case = recovery_case
    before = _read(case).json()
    original = case["originals"][0]
    receipt = _retry(case, original)
    assert receipt.status_code == 202
    job_id = UUID(receipt.json()["collection_job_id"])
    # A newer confirmed fact must survive any subsequent failed collection.
    with Session(case["engine"]) as session:
        OperatingDashboardService(session).repository.upsert_daily_metric(
            shop_id=original[2], business_date=original[3], source_code="douyin_compass_core_index_v3",
            metric_contract="douyin_compass_daily_v2_refund_orders", turnover_cents=123, order_count=2,
            refund_order_count=9, refund_order_status="available", collected_at=datetime.now(UTC))
        session.commit()
    platform = SyntheticPlatform(case, reject_identity=True)
    platform.install(monkeypatch)
    assert platform.executor().execute_available(collection_job_id=job_id) == 1
    assert (platform.identity_calls, platform.metric_calls) == (1, 0)
    status = _api(case, "GET", f"/api/v1/operating-dashboard/collections/{job_id}").json()
    assert status["status"] == "failed"
    assert status["items"][0]["retryable"] is False
    assert status["items"][0]["attempt_count"] == 1
    assert _retry(case, original).json()["collection_job_id"] == str(job_id)
    assert platform.executor().execute_available(collection_job_id=job_id) == 0
    with Session(case["engine"]) as session:
        stored = session.scalar(select(ShopSession).where(ShopSession.shop_id == original[2]))
        stored.version += 1
        stored.validated_at = datetime.now(UTC)
        session.commit()
        metric = session.scalar(select(ShopOperatingDailyMetric).where(
            ShopOperatingDailyMetric.shop_id == original[2], ShopOperatingDailyMetric.business_date == original[3]))
        assert (metric.turnover_cents, metric.order_count, metric.refund_order_count) == (123, 2, 9)
        assert session.get(OperatingDataCollectionItem, original[1]).attempt_count == 3
    assert _retry(case, original).json()["collection_job_id"] == str(job_id)
    assert (platform.identity_calls, platform.metric_calls) == (1, 0)
    evidence = Path(__file__).resolve().parents[3] / ".codex" / "operating-session-recovery-v1-20261017"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "validation-failure-api-proof.json").write_text(json.dumps({
        "kind": "FEATURE_POSTGRESQL_WITH_SYNTHETIC_PLATFORM_NOT_PRODUCTION",
        "before": before, "accepted": receipt.json(), "finished": status, "after": _read(case).json(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def test_recovery_rechecks_team_access_before_claim_and_keeps_other_teams_isolated(recovery_case, monkeypatch):
    case = recovery_case
    original = case["originals"][0]
    assert _retry(case, original, outsider=True).status_code == 404
    assert _read(case, outsider=True).json()["table"]["total"] == 0
    receipt = _retry(case, original)
    assert receipt.status_code == 202
    job_id = UUID(receipt.json()["collection_job_id"])
    with Session(case["engine"]) as session:
        session.execute(delete(TeamShopAccess).where(
            TeamShopAccess.team_id == case["ids"]["team"], TeamShopAccess.shop_id == original[2]))
        session.commit()
    platform = SyntheticPlatform(case)
    platform.install(monkeypatch)
    assert platform.executor().execute_available(collection_job_id=job_id) == 1
    assert (platform.identity_calls, platform.metric_calls) == (0, 0)
    assert _api(case, "GET", f"/api/v1/operating-dashboard/collections/{job_id}").status_code == 404
    with Session(case["engine"]) as session:
        item = session.scalar(select(OperatingDataCollectionItem).where(OperatingDataCollectionItem.collection_job_id == job_id))
        assert item.status == "skipped" and item.failure_code == "COLLECTION_REQUESTER_ACCESS_REVOKED"


def test_default_freshness_boundary_is_preserved_without_deferred_opt_in(recovery_case):
    case = recovery_case
    now = datetime.now(UTC)
    for original, age, allowed in zip(case["originals"][:2], (300, 301), (True, False), strict=True):
        with Session(case["engine"]) as session:
            stored = session.scalar(select(ShopSession).where(ShopSession.shop_id == original[2]))
            stored.validated_at = now - timedelta(seconds=age)
            session.commit()
            actor = ActorContextService(session).resolve(user_id=case["ids"]["user"], requested_team_id=case["ids"]["team"])
            service = OperatingDashboardService(session, settings=case["settings"])
            if allowed:
                result = service.retry_failed_collection_items(actor=actor, collection_job_id=original[0],
                    item_ids=[original[1]], session_recovery_version=3, now=now)
                assert result.counts.pending == 1
            else:
                from app.modules.operating_dashboard.exceptions import OperatingDashboardCollectionRetryUnavailableError
                with pytest.raises(OperatingDashboardCollectionRetryUnavailableError):
                    service.retry_failed_collection_items(actor=actor, collection_job_id=original[0],
                        item_ids=[original[1]], session_recovery_version=3, now=now)


def test_health_default_does_not_release_a_callers_flushed_transaction(recovery_case):
    case = recovery_case
    with Session(case["engine"]) as session:
        user = session.get(User, case["ids"]["user"])
        previous = user.display_name
        user.display_name = "stage-2a1 caller-owned uncommitted edit"
        session.flush()
        assert not session.dirty  # Flushed writes cannot be detected by dirty alone.
        class TimeoutConnector:
            def fetch_shop_identity(self, shop_id, context):
                assert session.in_transaction()
                raise PlatformRequestTimeoutError()
        health = ShopSessionHealthService(session, ShopSessionAccessor(session, case["cipher"]),
            {ShopPlatform.DOUYIN: TimeoutConnector()},
            session_service=ShopSessionService(session, case["cipher"]), settings=case["settings"])
        with pytest.raises(PlatformRequestTimeoutError):
            health.check(case["ids"]["shop1"], force=False)
        assert session.in_transaction()
        assert user.display_name == "stage-2a1 caller-owned uncommitted edit"
        with Session(case["engine"]) as other:
            assert other.get(User, case["ids"]["user"]).display_name == previous
        session.rollback()
        assert session.get(User, case["ids"]["user"]).display_name == previous


def test_one_shot_recovery_lease_expiry_never_accepts_a_late_result(recovery_case):
    from app.platforms.douyin.operating_data import CompassDailyMetrics
    from app.platforms.douyin.operating_data_executor import CollectionOutcome, CollectionStage, CollectionStatus, CollectionTimings, DailyCollectionRequest
    case = recovery_case
    original = case["originals"][0]
    receipt = _retry(case, original)
    assert receipt.status_code == 202
    job_id = UUID(receipt.json()["collection_job_id"])
    now = datetime.now(UTC)
    with Session(case["engine"]) as session:
        service = OperatingDashboardService(session, settings=case["settings"])
        claim = service.prepare_next_collection(now=now, lease_until=now + timedelta(seconds=30), collection_job_id=job_id)
        assert claim and claim.attempt_count == 1
        assert service.prepare_next_collection(now=now + timedelta(seconds=60), lease_until=now + timedelta(seconds=120), collection_job_id=job_id) is None
        outcome = CollectionOutcome(request=DailyCollectionRequest(original[2], original[3]),
            status=CollectionStatus.SUCCEEDED, stage=CollectionStage.COMPLETE,
            retryable=False, requires_reauthorization=False,
            metrics=CompassDailyMetrics(0, 0, 3, "available"), timings=CollectionTimings())
        assert not service.finalize_collection(claim=claim, outcome=outcome, now=now + timedelta(seconds=61))
        items = service.repository.list_job_items(collection_job_id=job_id)
        assert len(items) == 1 and items[0].status == "failed" and not items[0].retryable
        assert service.repository.list_metrics(shop_ids=[original[2]], start_date=original[3], end_date=original[3]) == []


def test_cookie_update_cannot_overwrite_a_concurrently_newer_session(recovery_case, monkeypatch):
    case = recovery_case
    original = case["originals"][0]
    response = _retry(case, original)
    assert response.status_code == 202
    job_id = UUID(response.json()["collection_job_id"])
    with Session(case["engine"]) as session:
        payload_before = session.scalar(select(ShopSession.payload_encrypted).where(ShopSession.shop_id == original[2]))
    platform = SyntheticPlatform(case, cookie_version_conflict=True)
    platform.install(monkeypatch)
    assert platform.executor().execute_available(collection_job_id=job_id) == 1
    assert (platform.identity_calls, platform.metric_calls) == (1, 0)
    with Session(case["engine"]) as session:
        stored = session.scalar(select(ShopSession).where(ShopSession.shop_id == original[2]))
        assert stored.version == 4 and stored.payload_encrypted == payload_before
        item = session.scalar(select(OperatingDataCollectionItem).where(OperatingDataCollectionItem.collection_job_id == job_id))
        assert item.status == "failed" and not item.retryable
        assert item.failure_code == "SHOP_SESSION_VERSION_CONFLICT"


def test_explicit_deferred_recovery_still_rejects_disabled_or_changed_session_context(recovery_case):
    case = recovery_case
    original = case["originals"][0]
    with Session(case["engine"]) as session:
        stored = session.scalar(select(ShopSession).where(ShopSession.shop_id == original[2]))
        stored.version = 4
        session.commit()
    assert _retry(case, original).status_code == 409
    with Session(case["engine"]) as session:
        stored = session.scalar(select(ShopSession).where(ShopSession.shop_id == original[2]))
        stored.version = 3
        stored.validated_at = datetime.now(UTC) + timedelta(days=1)
        session.commit()
    assert _retry(case, original).status_code == 409
    with Session(case["engine"]) as session:
        stored = session.scalar(select(ShopSession).where(ShopSession.shop_id == original[2]))
        stored.validated_at = datetime.now(UTC) - timedelta(minutes=34)
        session.get(Shop, original[2]).enabled = False
        session.commit()
    assert _retry(case, original).status_code == 409
    with Session(case["engine"]) as session:
        assert session.scalar(select(func.count()).select_from(OperatingDataCollectionItem).where(
            OperatingDataCollectionItem.shop_id.in_((case["ids"]["shop1"], case["ids"]["shop2"])))) == 8
