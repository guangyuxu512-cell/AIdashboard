from collections import defaultdict
from datetime import date, timedelta
from threading import Lock
from time import sleep
from uuid import UUID, uuid4

from app.modules.sessions.auth_context import ShopSessionAuthContext, StoredSessionCookie
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.operating_data import (
    CompassDailyMetrics,
    CompassDailyRead,
    DouyinOperatingDataMetricUnavailableError,
)
from app.platforms.douyin.operating_data_executor import (
    CollectionOutcome,
    CollectionStage,
    CollectionStatus,
    CollectionTimings,
    DailyCollectionRequest,
    DouyinOperatingDataBatchExecutor,
    SessionAwareDouyinOperatingDataCollector,
    ShopCollectionGuard,
)
from app.platforms.exceptions import (
    PlatformAuthenticationInvalidError,
    PlatformResponseInvalidError,
    PlatformSignerFailedError,
)


DAY = date(2026, 9, 19)


def _success(request: DailyCollectionRequest) -> CollectionOutcome:
    return CollectionOutcome(
        request=request,
        status=CollectionStatus.SUCCEEDED,
        stage=CollectionStage.COMPLETE,
        retryable=False,
        requires_reauthorization=False,
        timings=CollectionTimings(total_ms=1),
        metrics=CompassDailyMetrics(1, 1),
    )


def _failure(
    request: DailyCollectionRequest,
    *,
    requires_reauthorization: bool = False,
) -> CollectionOutcome:
    return CollectionOutcome(
        request=request,
        status=CollectionStatus.FAILED,
        stage=CollectionStage.SESSION_PREPARATION,
        retryable=not requires_reauthorization,
        requires_reauthorization=requires_reauthorization,
        failure_code=(
            "SHOP_REAUTHORIZATION_REQUIRED"
            if requires_reauthorization
            else "SYNTHETIC_FAILURE"
        ),
        timings=CollectionTimings(total_ms=1),
    )


def test_batch_limits_to_five_and_backfills_after_each_completion() -> None:
    lock = Lock()
    active = 0
    highest_active = 0
    completed: list[UUID] = []

    def collector(request: DailyCollectionRequest) -> CollectionOutcome:
        nonlocal active, highest_active
        with lock:
            active += 1
            highest_active = max(highest_active, active)
        sleep(0.03)
        with lock:
            active -= 1
            completed.append(request.shop_id)
        return _success(request)

    requests = [DailyCollectionRequest(uuid4(), DAY) for _ in range(7)]
    outcomes = DouyinOperatingDataBatchExecutor(
        collector,
        max_concurrency=5,
        guard=ShopCollectionGuard(),
    ).execute(requests)

    assert highest_active == 5
    assert len(completed) == 7
    assert all(outcome.status is CollectionStatus.SUCCEEDED for outcome in outcomes)
    assert all(outcome.timings.queue_wait_ms >= 0 for outcome in outcomes)


def test_batch_serializes_one_shop_skips_same_day_duplicate_and_isolates_failure() -> None:
    shop_a = uuid4()
    shop_b = uuid4()
    active_by_shop: defaultdict[UUID, int] = defaultdict(int)
    max_active_by_shop: defaultdict[UUID, int] = defaultdict(int)
    calls: list[DailyCollectionRequest] = []
    lock = Lock()

    def collector(request: DailyCollectionRequest) -> CollectionOutcome:
        with lock:
            active_by_shop[request.shop_id] += 1
            max_active_by_shop[request.shop_id] = max(
                max_active_by_shop[request.shop_id],
                active_by_shop[request.shop_id],
            )
            calls.append(request)
        sleep(0.02)
        with lock:
            active_by_shop[request.shop_id] -= 1
        if request.shop_id == shop_b:
            return _failure(request)
        return _success(request)

    requests = [
        DailyCollectionRequest(shop_a, DAY),
        DailyCollectionRequest(shop_b, DAY),
        DailyCollectionRequest(shop_a, DAY + timedelta(days=1)),
        DailyCollectionRequest(shop_a, DAY),
    ]
    outcomes = DouyinOperatingDataBatchExecutor(
        collector,
        max_concurrency=5,
        guard=ShopCollectionGuard(),
    ).execute(requests)

    assert max_active_by_shop[shop_a] == 1
    assert len([item for item in calls if item.shop_id == shop_a]) == 2
    assert outcomes[1].status is CollectionStatus.FAILED
    assert outcomes[3].status is CollectionStatus.SKIPPED
    assert outcomes[3].failure_code == "DUPLICATE_SHOP_DATE"
    assert outcomes[2].status is CollectionStatus.SUCCEEDED


def test_reauthorization_pauses_only_remaining_requests_for_that_shop() -> None:
    shop_a = uuid4()
    shop_b = uuid4()
    calls: list[UUID] = []

    def collector(request: DailyCollectionRequest) -> CollectionOutcome:
        calls.append(request.shop_id)
        if request.shop_id == shop_a:
            return _failure(request, requires_reauthorization=True)
        return _success(request)

    requests = [
        DailyCollectionRequest(shop_a, DAY),
        DailyCollectionRequest(shop_b, DAY),
        DailyCollectionRequest(shop_a, DAY + timedelta(days=1)),
    ]
    outcomes = DouyinOperatingDataBatchExecutor(
        collector,
        max_concurrency=2,
        guard=ShopCollectionGuard(),
    ).execute(requests)

    assert calls.count(shop_a) == 1
    assert calls.count(shop_b) == 1
    assert outcomes[0].requires_reauthorization is True
    assert outcomes[1].status is CollectionStatus.SUCCEEDED
    assert outcomes[2].status is CollectionStatus.PAUSED_REAUTHORIZATION
    assert outcomes[2].failure_code == "SHOP_REAUTHORIZATION_REQUIRED"


def test_process_guard_rejects_an_overlapping_same_shop_collection() -> None:
    shop_id = uuid4()
    guard = ShopCollectionGuard()
    request = DailyCollectionRequest(shop_id, DAY)

    with guard.try_acquire(shop_id) as acquired:
        assert acquired is True
        outcome = DouyinOperatingDataBatchExecutor(
            _success,
            guard=guard,
        ).execute([request])[0]

    assert outcome.status is CollectionStatus.SKIPPED
    assert outcome.failure_code == "SHOP_COLLECTION_IN_PROGRESS"


class _FakeHealthService:
    def __init__(self) -> None:
        self.applied_updates = []

    def check(self, shop_id: UUID, *, force: bool) -> object:
        assert force is False
        return object()

    def apply_response_cookie_updates(
        self,
        context,
        updates,
    ) -> int:  # type: ignore[no-untyped-def]
        self.applied_updates.append((context, updates))
        return len(updates)


class _FakeAccessor:
    def __init__(self, context: ShopSessionAuthContext) -> None:
        self.context = context
        self.marked: list[ShopSessionStatus] = []

    def get_auth_context(
        self,
        shop_id: UUID,
        platform: ShopPlatform,
    ) -> ShopSessionAuthContext:
        assert shop_id == self.context.shop_id
        assert platform is ShopPlatform.DOUYIN
        return self.context

    def mark_validation_status(
        self,
        shop_id: UUID,
        expected_version: int,
        status: ShopSessionStatus,
    ) -> None:
        assert shop_id == self.context.shop_id
        assert expected_version == self.context.session_version
        self.marked.append(status)


class _FakeConnector:
    def __init__(self, result: CompassDailyRead | Exception) -> None:
        self.result = result

    def fetch_daily_metrics(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        del args, kwargs
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _session_collector(
    result: CompassDailyRead | Exception,
) -> tuple[SessionAwareDouyinOperatingDataCollector, _FakeHealthService, _FakeAccessor]:
    shop_id = uuid4()
    context = ShopSessionAuthContext(
        shop_id=shop_id,
        platform=ShopPlatform.DOUYIN,
        session_version=4,
        cookies=(),
    )
    health = _FakeHealthService()
    accessor = _FakeAccessor(context)
    return (
        SessionAwareDouyinOperatingDataCollector(
            health_service=health,  # type: ignore[arg-type]
            session_accessor=accessor,  # type: ignore[arg-type]
            connector=_FakeConnector(result),  # type: ignore[arg-type]
        ),
        health,
        accessor,
    )


def test_session_aware_collector_classifies_signer_and_auth_failures() -> None:
    signer_collector, _, signer_accessor = _session_collector(
        PlatformSignerFailedError(details={"retryable": True}),
    )
    signer_request = DailyCollectionRequest(signer_accessor.context.shop_id, DAY)
    signer_outcome = signer_collector.collect(signer_request)

    assert signer_outcome.stage is CollectionStage.SIGNING
    assert signer_outcome.retryable is True
    assert signer_outcome.requires_reauthorization is False
    assert signer_accessor.marked == []

    auth_collector, _, auth_accessor = _session_collector(
        PlatformAuthenticationInvalidError(),
    )
    auth_outcome = auth_collector.collect(
        DailyCollectionRequest(auth_accessor.context.shop_id, DAY),
    )

    assert auth_outcome.failure_code == "SHOP_REAUTHORIZATION_REQUIRED"
    assert auth_outcome.requires_reauthorization is True
    assert auth_accessor.marked == [ShopSessionStatus.INVALID]


def test_session_aware_collector_keeps_required_metric_parse_hint_safe() -> None:
    collector, _, accessor = _session_collector(
        PlatformResponseInvalidError(
            details={"failure_stage": "core_index_parse", "metric": "pay_cnt"},
        ),
    )

    outcome = collector.collect(DailyCollectionRequest(accessor.context.shop_id, DAY))

    assert outcome.stage is CollectionStage.RESPONSE_PARSE
    assert outcome.failure_code == "DOUYIN_OPERATING_DATA_INVALID_RESPONSE"
    assert outcome.failure_message == "抖店经营数据响应缺少或无法读取必要指标：成交订单数"
    assert outcome.retryable is False


def test_session_aware_collector_marks_a_known_scalarless_core_value_unknown() -> None:
    collector, _, accessor = _session_collector(
        DouyinOperatingDataMetricUnavailableError(
            details={"failure_stage": "core_index_parse", "metric": "income_amt"},
        ),
    )

    outcome = collector.collect(DailyCollectionRequest(accessor.context.shop_id, DAY))

    assert outcome.stage is CollectionStage.RESPONSE_PARSE
    assert outcome.failure_code == "DOUYIN_OPERATING_DATA_METRICS_UNAVAILABLE"
    assert outcome.failure_message == "抖店平台未提供可确认的经营指标值"
    assert outcome.retryable is False
    assert outcome.requires_reauthorization is False


def test_session_aware_collector_persists_only_explicit_response_cookie_updates() -> None:
    shop_id = uuid4()
    read = CompassDailyRead(
        shop_id=shop_id,
        statistic_date=DAY,
        metrics=CompassDailyMetrics(98660, 93),
        cookie_updates=(
            StoredSessionCookie(name="rotated", value="synthetic-cookie"),
        ),
        signature_duration_ms=10,
        platform_duration_ms=20,
        parse_duration_ms=1,
    )
    collector, health, accessor = _session_collector(read)
    # Use the collector's authoritative ShopSession identity; the fake read
    # carries no session information and its shop_id is not a permission key.
    outcome = collector.collect(DailyCollectionRequest(accessor.context.shop_id, DAY))

    assert outcome.status is CollectionStatus.SUCCEEDED
    assert len(health.applied_updates) == 1
    assert outcome.timings.signature_ms == 10
    assert outcome.timings.platform_response_ms == 20
    assert outcome.timings.response_parse_ms == 1
