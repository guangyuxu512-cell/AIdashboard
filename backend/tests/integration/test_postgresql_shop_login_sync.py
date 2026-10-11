"""Real PostgreSQL; all platform responses and credentials are synthetic."""
import base64
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.security import SecretCipher
from app.modules.access.exceptions import HumanUserDisabledError
from app.modules.access.models import Team, TeamMembership, TeamModuleAccess, TeamShopAccess
from app.modules.access.module_access import ModuleCode
from app.modules.access.service import ActorContextService
from app.modules.operating_dashboard.enums import SESSION_RESTORE_DEDUPE_PREFIX
from app.modules.operating_dashboard.exceptions import (
    OperatingDashboardCollectionNotFoundError,
    OperatingDashboardCollectionRetryUnavailableError,
)
from app.modules.operating_dashboard.models import OperatingDataCollectionItem, OperatingDataCollectionJob
from app.modules.operating_dashboard.service import (
    DOUYIN_CORE_INDEX_CONTRACT, DOUYIN_CORE_INDEX_SOURCE, OperatingDashboardService,
)
from app.modules.sessions.auth_context import ShopSessionAccessor, StoredSessionCookie
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import (
    SessionRefreshLeaseConflictError, SessionVersionConflictError, ShopSessionNotConfiguredError,
    ShopSessionPayloadInvalidError,
)
from app.modules.sessions.health_service import ShopSessionHealthService
from app.modules.sessions.models import ShopSession
from app.modules.sessions.refresh_service import ShopSessionRefreshService
from app.modules.sessions.schemas import CompleteShopSessionRefreshCommand, StoreShopSessionCommand
from app.modules.sessions.service import ShopSessionService
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.users.models import User
from app.platforms.douyin.operating_data_executor import (
    CollectionOutcome, CollectionStage, CollectionStatus, CollectionTimings, DailyCollectionRequest,
)
from app.platforms.exceptions import (
    PlatformAuthenticationInvalidError, PlatformIdentityMismatchError, PlatformRequestFailedError,
    PlatformRequestTimeoutError, PlatformResponseInvalidError, PlatformSignerFailedError,
)
from app.platforms.schemas import PlatformShopIdentity
from tests.integration.test_postgresql_operating_dashboard import _cleanup, _settings, _success

pytestmark = pytest.mark.integration
NOW = datetime(2026, 10, 11, 10, tzinfo=UTC)
DAY = date(2026, 10, 10)


@pytest.fixture
def sync_fixture(postgresql_engine):
    # Integration may independently run this suite; Owner always uses its
    # registered exclusive Feature database, never another Feature's database.
    assert postgresql_engine.url.database in {
        "control_center_feat_shop_login_session_sync", "control_center_integration",
    }
    ids = {"user": uuid4(), "team": uuid4(), "other_team": uuid4(), "shop": uuid4()}
    with Session(postgresql_engine) as session:
        session.add_all([
            User(user_id=ids["user"], display_name="stage-2a1 login sync member"),
            Team(team_id=ids["team"], name=f"stage-2a1 sync {ids['team']}"),
            Team(team_id=ids["other_team"], name=f"stage-2a1 sync {ids['other_team']}"),
            Shop(shop_id=ids["shop"], display_name="stage-2a1 login sync shop",
                 platform=ShopPlatform.DOUYIN, platform_shop_id="synthetic-shop", enabled=True),
        ])
        session.flush()
        session.add_all([
            TeamMembership(user_id=ids["user"], team_id=ids["team"], enabled=True),
            TeamModuleAccess(team_id=ids["team"], module_code=ModuleCode.SHOP.value),
            TeamModuleAccess(team_id=ids["other_team"], module_code=ModuleCode.SHOP.value),
            TeamShopAccess(team_id=ids["team"], shop_id=ids["shop"]),
        ])
        session.commit()
    cipher = SecretCipher(Fernet.generate_key().decode())
    try:
        yield postgresql_engine, ids, cipher
    finally:
        with Session(postgresql_engine) as session:
            session.execute(delete(ShopSession).where(ShopSession.shop_id == ids["shop"]))
            session.commit()
        _cleanup(postgresql_engine, {ids["shop"]})
        with Session(postgresql_engine) as session:
            session.execute(delete(TeamMembership).where(TeamMembership.user_id == ids["user"]))
            session.execute(delete(TeamModuleAccess).where(TeamModuleAccess.team_id.in_([ids["team"], ids["other_team"]])))
            session.execute(delete(Team).where(Team.team_id.in_([ids["team"], ids["other_team"]])))
            session.execute(delete(User).where(User.user_id == ids["user"]))
            session.commit()


def _payload(platform="douyin", *, identity="synthetic-shop"):
    return json.dumps({
        "schema": "management-login.session.v1", "platform": platform,
        "identity": {"platform": platform, "platformShopId": identity, "shopDisplayName": "fixture"},
        "cookies": [{"name": "sessionid", "value": "synthetic-only", "domain": ".jinritemai.com", "path": "/"}],
    }).encode()


class Connector:
    def __init__(self, session, *, failure=None, callback=None, cookie_updates=()):
        self.session, self.failure, self.callback = session, failure, callback
        self.cookie_updates = cookie_updates
        self.calls = 0

    def fetch_shop_identity(self, shop_id, context):
        self.calls += 1
        assert not self.session.in_transaction(), "platform I/O held a database transaction"
        assert context.shop_id == shop_id
        if self.callback:
            self.callback()
        if self.failure:
            raise self.failure
        return PlatformShopIdentity(
            platform_shop_id="synthetic-shop", shop_display_name="fixture",
            cookie_updates=self.cookie_updates,
        )


def _refresh(session, cipher, connector=None, *, resume=None):
    connector = connector or Connector(session)
    health = ShopSessionHealthService(
        session, ShopSessionAccessor(session, cipher),
        {ShopPlatform.DOUYIN: connector, ShopPlatform.PDD: connector},
        session_service=ShopSessionService(session, cipher),
    )
    return ShopSessionRefreshService(session, cipher, health, collection_resume=resume or (lambda _: 0))


def _command(lease, *, platform="douyin"):
    return CompleteShopSessionRefreshCommand(
        lease_id=lease.lease_id, expected_version=lease.expected_version,
        session_payload_base64=SecretStr(base64.b64encode(_payload(platform)).decode()),
        captured_at=datetime.now(UTC),
    )


def _seed_valid(session, ids, cipher, *, captured_at=None, validated_at=None):
    session.add(ShopSession(
        shop_id=ids["shop"], version=1, status=ShopSessionStatus.VALID,
        captured_at=captured_at or NOW - timedelta(seconds=10),
        validated_at=validated_at or NOW - timedelta(seconds=5),
        payload_encrypted=cipher.encrypt_bytes(_payload()),
    ))
    session.commit()


def _fields(stored):
    return (stored.version, stored.status, stored.payload_encrypted, stored.captured_at, stored.validated_at)


def test_first_existing_shop_concurrent_reservation_cancel_and_accessor(sync_fixture):
    engine, ids, cipher = sync_fixture
    barrier = Barrier(2)

    def acquire():
        with Session(engine) as session:
            service = _refresh(session, cipher)
            barrier.wait(timeout=10)
            try:
                return service.acquire(ids["shop"])
            except SessionRefreshLeaseConflictError:
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: acquire(), range(2)))
    leases = [lease for lease in results if lease is not None]
    assert len(leases) == 1 and leases[0].expected_version == 1
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(ShopSession).where(ShopSession.shop_id == ids["shop"])) == 1
        metadata = ShopSessionService(session).get_metadata(ids["shop"])
        assert not metadata.configured and metadata.captured_at is None and metadata.validated_at is None
        assert metadata.refresh_in_progress and metadata.status is ShopSessionStatus.NOT_CONFIGURED
        class NoDecrypt:
            def decrypt_bytes(self, _):
                pytest.fail("NOT_CONFIGURED was decrypted")
        with pytest.raises(ShopSessionNotConfiguredError):
            ShopSessionAccessor(session, NoDecrypt()).get_auth_context(ids["shop"], ShopPlatform.DOUYIN)
        _refresh(session, cipher).release(ids["shop"], leases[0].lease_id)
        metadata = ShopSessionService(session).get_metadata(ids["shop"])
        assert not metadata.refresh_in_progress and not metadata.configured


@pytest.mark.parametrize("platform", [ShopPlatform.DOUYIN, ShopPlatform.PDD])
def test_reserved_session_verified_once_commits_v2_and_releases_lease(sync_fixture, platform):
    engine, ids, cipher = sync_fixture
    with Session(engine) as session:
        session.get(Shop, ids["shop"]).platform = platform
        session.commit()
        connector = Connector(session)
        service = _refresh(session, cipher, connector)
        lease = service.acquire(ids["shop"])
        result = service.complete(ids["shop"], _command(lease, platform=platform.value))
        assert connector.calls == 1 and result.version == 2 and not result.used_cached_validation
        metadata = ShopSessionService(session).get_metadata(ids["shop"])
        assert metadata.configured and metadata.status is ShopSessionStatus.VALID
        assert not metadata.refresh_in_progress
        assert ShopSessionAccessor(session, cipher).get_auth_context(ids["shop"], platform).session_version == 2


def test_candidate_response_cookie_updates_are_saved_only_after_fresh_validation(sync_fixture):
    engine, ids, cipher = sync_fixture
    with Session(engine) as session:
        _seed_valid(session, ids, cipher)
        updates = (StoredSessionCookie(
            name="sessionid", value=SecretStr("synthetic-rotated"),
            domain=".jinritemai.com", path="/",
        ),)
        connector = Connector(session, cookie_updates=updates)
        service = _refresh(session, cipher, connector)
        lease = service.acquire(ids["shop"])
        result = service.complete(ids["shop"], _command(lease))
        assert result.version == 2 and result.cookie_updates_applied == 1
        assert connector.calls == 1 and not result.used_cached_validation
        context = ShopSessionAccessor(session, cipher).get_auth_context(ids["shop"], ShopPlatform.DOUYIN)
        assert context.cookies[0].value.get_secret_value() == "synthetic-rotated"


def test_unconfigured_expired_lease_can_be_reacquired_without_fake_capture(sync_fixture):
    engine, ids, cipher = sync_fixture
    with Session(engine) as session:
        service = _refresh(session, cipher)
        first = service.acquire(ids["shop"])
        stored = session.scalar(select(ShopSession).where(ShopSession.shop_id == ids["shop"]))
        stored.refresh_lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
        second = service.acquire(ids["shop"])
        assert second.lease_id != first.lease_id and second.expected_version == 1
        metadata = ShopSessionService(session).get_metadata(ids["shop"])
        assert not metadata.configured and metadata.captured_at is None
        assert metadata.validated_at is None and metadata.refresh_in_progress
        service.release(ids["shop"], second.lease_id)


@pytest.mark.parametrize("has_original", [False, True])
@pytest.mark.parametrize("failure", [
    PlatformAuthenticationInvalidError(), PlatformIdentityMismatchError(), PlatformRequestFailedError(),
    PlatformSignerFailedError(), PlatformRequestTimeoutError(), PlatformResponseInvalidError(),
])
def test_invalid_replacement_preserves_original_or_unconfigured_reservation(sync_fixture, has_original, failure):
    engine, ids, cipher = sync_fixture
    with Session(engine) as session:
        if has_original:
            _seed_valid(session, ids, cipher)
        connector = Connector(session, failure=failure)
        service = _refresh(session, cipher, connector)
        lease = service.acquire(ids["shop"])
        before = _fields(session.scalar(select(ShopSession).where(ShopSession.shop_id == ids["shop"])))
        with pytest.raises(type(failure)):
            service.complete(ids["shop"], _command(lease))
        session.expire_all()
        stored = session.scalar(select(ShopSession).where(ShopSession.shop_id == ids["shop"]))
        assert _fields(stored) == before and stored.refresh_lease_id is None


@pytest.mark.parametrize("interruption", ["cancel", "expired", "version", "permission", "identity"])
def test_late_candidate_cannot_overwrite_after_concurrent_change(sync_fixture, interruption):
    engine, ids, cipher = sync_fixture
    with Session(engine) as session:
        _seed_valid(session, ids, cipher)
        service = _refresh(session, cipher)
        lease = service.acquire(ids["shop"])
        before = _fields(session.scalar(select(ShopSession).where(ShopSession.shop_id == ids["shop"])))
        def change():
            with Session(engine) as other:
                stored = other.scalar(select(ShopSession).where(ShopSession.shop_id == ids["shop"]))
                if interruption == "cancel":
                    _refresh(other, cipher).release(ids["shop"], lease.lease_id)
                elif interruption == "expired":
                    stored.refresh_lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
                elif interruption == "version":
                    stored.version += 1
                elif interruption == "permission":
                    other.get(User, ids["user"]).enabled = False
                else:
                    other.get(Shop, ids["shop"]).platform_shop_id = "changed-target"
                other.commit()
        service = _refresh(session, cipher, Connector(session, callback=change))
        def reauthorize():
            ActorContextService(session).resolve(user_id=ids["user"], requested_team_id=ids["team"])
        expected_error = (
            HumanUserDisabledError if interruption == "permission"
            else ShopSessionPayloadInvalidError if interruption == "identity"
            else SessionVersionConflictError
        )
        with pytest.raises(expected_error):
            service.complete(ids["shop"], _command(lease), recheck_authorization=reauthorize)
        session.expire_all()
        stored = session.scalar(select(ShopSession).where(ShopSession.shop_id == ids["shop"]))
        assert _fields(stored)[1:] == before[1:]
        assert stored.version == before[0] + (interruption == "version")


def _original_failed_daily(session, ids, *, kind="daily"):
    job = OperatingDataCollectionJob(
        kind=kind, status="failed", requested_start_date=DAY, requested_end_date=DAY,
    )
    session.add(job)
    session.flush()
    item = OperatingDataCollectionItem(
        collection_job_id=job.collection_job_id, shop_id=ids["shop"], business_date=DAY,
        status="failed", attempt_count=3, retryable=True,
        failure_code="SHOP_SESSION_VALIDATION_FAILED", failure_stage="session_preparation",
        finished_at=NOW - timedelta(minutes=10),
    )
    session.add(item)
    session.commit()
    return job.collection_job_id, item.collection_item_id


def _retry(session, ids, job_id, item_id, **settings):
    actor = ActorContextService(session).resolve(user_id=ids["user"], requested_team_id=ids["team"])
    return OperatingDashboardService(session, settings=_settings(**settings)).retry_failed_collection_items(
        actor=actor, collection_job_id=job_id, item_ids=[item_id], session_recovery_version=1, now=NOW,
    )


def _claim(service, job_id, *, now=NOW):
    return service.prepare_next_collection(
        now=now, lease_until=now + timedelta(seconds=60), collection_job_id=job_id,
    )


def test_explicit_recovery_cross_connection_dedupe_single_claim_success_and_history(sync_fixture):
    engine, ids, cipher = sync_fixture
    with Session(engine) as session:
        _seed_valid(session, ids, cipher)
        job_id, item_id = _original_failed_daily(session, ids)
    barrier = Barrier(2)
    def submit():
        with Session(engine) as session:
            barrier.wait(timeout=10)
            return _retry(session, ids, job_id, item_id).collection_job_id
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(), range(2)))
    assert results[0] == results[1]
    with Session(engine) as session:
        assert session.get(OperatingDataCollectionJob, results[0]).dedupe_key == f"{SESSION_RESTORE_DEDUPE_PREFIX}{item_id}"
        service = OperatingDashboardService(session, settings=_settings())
        claim = _claim(service, results[0])
        assert claim and claim.attempt_count == 1
        with Session(engine) as other:
            assert _claim(OperatingDashboardService(other, settings=_settings()), results[0]) is None
        assert service.finalize_collection(claim=claim, outcome=_success(DailyCollectionRequest(ids["shop"], DAY), refund_observed=True), now=NOW)
        session.expire_all()
        original = session.get(OperatingDataCollectionItem, item_id)
        assert original.status == "failed" and original.attempt_count == 3
        assert _retry(session, ids, job_id, item_id).collection_job_id == results[0]
        session.execute(delete(TeamShopAccess).where(TeamShopAccess.shop_id == ids["shop"]))
        session.commit()
        with pytest.raises(OperatingDashboardCollectionNotFoundError):
            _retry(session, ids, job_id, item_id)


@pytest.mark.parametrize("age,allowed", [(299, True), (300, True), (301, False)])
def test_recovery_uses_existing_validation_freshness_boundary(sync_fixture, age, allowed):
    engine, ids, cipher = sync_fixture
    with Session(engine) as session:
        _seed_valid(session, ids, cipher, captured_at=NOW - timedelta(seconds=age + 1), validated_at=NOW - timedelta(seconds=age))
        job_id, item_id = _original_failed_daily(session, ids)
        if allowed:
            _retry(session, ids, job_id, item_id, shop_session_validation_freshness_seconds=300)
        else:
            with pytest.raises(OperatingDashboardCollectionRetryUnavailableError):
                _retry(session, ids, job_id, item_id, shop_session_validation_freshness_seconds=300)


@pytest.mark.parametrize("condition", ["disabled", "old_capture", "future_validation", "unknown_identity", "wrong_kind", "other_error", "active", "complete"])
def test_explicit_recovery_is_not_an_ordinary_retry_escape_hatch(sync_fixture, condition):
    engine, ids, cipher = sync_fixture
    with Session(engine) as session:
        _seed_valid(session, ids, cipher)
        job_id, item_id = _original_failed_daily(session, ids, kind="retry" if condition == "wrong_kind" else "daily")
        shop = session.get(Shop, ids["shop"])
        stored = session.scalar(select(ShopSession).where(ShopSession.shop_id == ids["shop"]))
        if condition == "disabled": shop.enabled = False
        elif condition == "old_capture": stored.captured_at = NOW - timedelta(days=1)
        elif condition == "future_validation": stored.validated_at = NOW + timedelta(seconds=1)
        elif condition == "unknown_identity": shop.platform_shop_id = None
        elif condition == "other_error": session.get(OperatingDataCollectionItem, item_id).failure_code = "PLATFORM_REQUEST_FAILED"
        elif condition == "active":
            # Same-date uniqueness requires a separate job.
            active_job = OperatingDataCollectionJob(kind="manual_refresh", status="pending", requested_start_date=DAY, requested_end_date=DAY)
            session.add(active_job); session.flush()
            session.add(OperatingDataCollectionItem(collection_job_id=active_job.collection_job_id, shop_id=ids["shop"], business_date=DAY, status="pending"))
        elif condition == "complete":
            OperatingDashboardService(session, settings=_settings()).repository.upsert_daily_metric(
                shop_id=ids["shop"], business_date=DAY, source_code=DOUYIN_CORE_INDEX_SOURCE, metric_contract=DOUYIN_CORE_INDEX_CONTRACT,
                turnover_cents=0, order_count=0, refund_order_count=0, refund_order_status="available", collected_at=NOW,
            )
        session.commit()
        with pytest.raises(OperatingDashboardCollectionRetryUnavailableError):
            _retry(session, ids, job_id, item_id)


@pytest.mark.parametrize("failure_kind", ["network", "authorization", "lease_expiry"])
def test_session_recovery_attempt_never_retries_pauses_or_accepts_late_result(sync_fixture, failure_kind):
    engine, ids, cipher = sync_fixture
    with Session(engine) as session:
        _seed_valid(session, ids, cipher)
        job_id, item_id = _original_failed_daily(session, ids)
        recovery = _retry(session, ids, job_id, item_id)
        service = OperatingDashboardService(session, settings=_settings())
        claim = _claim(service, recovery.collection_job_id)
        assert claim
        if failure_kind == "lease_expiry":
            assert _claim(service, recovery.collection_job_id, now=NOW + timedelta(minutes=2)) is None
            assert not service.finalize_collection(claim=claim, outcome=_success(DailyCollectionRequest(ids["shop"], DAY)), now=NOW + timedelta(minutes=2))
        else:
            outcome = CollectionOutcome(
                request=DailyCollectionRequest(ids["shop"], DAY), status=CollectionStatus.FAILED,
                stage=CollectionStage.SESSION_PREPARATION, retryable=True,
                requires_reauthorization=failure_kind == "authorization",
                failure_code="SHOP_SESSION_VALIDATION_FAILED", failure_message="synthetic failure", timings=CollectionTimings(),
            )
            assert service.finalize_collection(claim=claim, outcome=outcome, now=NOW)
        items = service.repository.list_job_items(collection_job_id=recovery.collection_job_id)
        assert len(items) == 1 and items[0].status == "failed" and not items[0].retryable
        assert items[0].attempt_count == 1
        assert _claim(service, recovery.collection_job_id, now=NOW + timedelta(days=1)) is None
        actor = ActorContextService(session).resolve(user_id=ids["user"], requested_team_id=ids["team"])
        with pytest.raises(OperatingDashboardCollectionRetryUnavailableError):
            service.retry_failed_collection_items(actor=actor, collection_job_id=job_id, item_ids=[item_id], now=NOW + timedelta(days=1))
