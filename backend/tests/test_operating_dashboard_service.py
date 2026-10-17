from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.modules.operating_dashboard.enums import OperatingCollectionItemStatus
from app.modules.operating_dashboard.exceptions import (
    OperatingDashboardInvalidRequestError,
)
from app.modules.operating_dashboard.models import ShopOperatingDailyMetric
from app.modules.operating_dashboard.repository import CollectionItemState, DashboardShop, SessionRecoveryMetadata
from app.modules.operating_dashboard.schemas import OperatingDashboardDateRangeRead
from app.modules.operating_dashboard.service import (
    COLLECTION_WAITING_FOR_DAILY_BOUNDARY,
    OperatingDashboardService,
    _is_session_recovery_failure,
    _session_recovery_block_reason,
    _session_recovery_requires_validation,
    _prioritized_collection_items,
    operating_collection_wait_until,
)
from app.modules.shops.enums import ShopPlatform
from app.modules.sessions.enums import ShopSessionStatus


@pytest.mark.parametrize("days", [1, 30, 60])
def test_manual_completed_range_accepts_one_to_sixty_calendar_days(days: int) -> None:
    end_date = date(2000, 12, 31)
    start_date = end_date - timedelta(days=days - 1)

    OperatingDashboardService._validate_completed_date_range(start_date, end_date)


def test_manual_completed_range_rejects_more_than_sixty_calendar_days() -> None:
    end_date = date(2000, 12, 31)
    start_date = end_date - timedelta(days=60)

    with pytest.raises(OperatingDashboardInvalidRequestError):
        OperatingDashboardService._validate_completed_date_range(start_date, end_date)


def _metric(
    *,
    shop_id: UUID,
    business_date: date,
    turnover_cents: int,
    order_count: int,
    refund_order_count: int | None = None,
    refund_order_status: str = "unobserved",
) -> ShopOperatingDailyMetric:
    return ShopOperatingDailyMetric(
        shop_id=shop_id,
        business_date=business_date,
        source_code="douyin_compass_core_index_v3",
        metric_contract="douyin_compass_daily_v1",
        turnover_cents=turnover_cents,
        order_count=order_count,
        refund_order_count=refund_order_count,
        refund_order_status=refund_order_status,
        collected_at=datetime(2026, 9, 20, tzinfo=UTC),
    )


def _collection_state(
    *,
    collection_item_id: UUID,
    failure_code: str = "DOUYIN_OPERATING_DATA_INVALID_RESPONSE",
    failure_stage: str | None = "response_parse",
    retryable: bool = False,
    attempt_count: int = 1,
    status: str = OperatingCollectionItemStatus.FAILED.value,
    updated_at: datetime = datetime(2026, 9, 23, tzinfo=UTC),
) -> CollectionItemState:
    return CollectionItemState(
        collection_item_id=collection_item_id,
        collection_job_id=uuid4(),
        shop_id=uuid4(),
        business_date=date(2026, 9, 22),
        status=status,
        retryable=retryable,
        attempt_count=attempt_count,
        failure_code=failure_code,
        failure_stage=failure_stage,
        finished_at=(
            updated_at
            if status == OperatingCollectionItemStatus.FAILED.value
            else None
        ),
        updated_at=updated_at,
        job_kind="daily",
        requested_by_user_id=None,
    )


def _recovery_service() -> OperatingDashboardService:
    return OperatingDashboardService(
        None,  # type: ignore[arg-type]
        settings=Settings(
            _env_file=None,
        ),
    )


@pytest.mark.parametrize(
    "kind,code,stage,retryable,status,allowed",
    [
        ("daily", "SHOP_SESSION_VALIDATION_FAILED", "session_preparation", True, "failed", True),
        ("manual_refresh", "SHOP_SESSION_VALIDATION_FAILED", "session_preparation", True, "failed", False),
        ("retry", "SHOP_SESSION_VALIDATION_FAILED", "session_preparation", True, "failed", False),
        ("daily", "DOUYIN_OPERATING_DATA_REJECTED", "platform_response", True, "failed", False),
        ("daily", "DOUYIN_OPERATING_DATA_INVALID_RESPONSE", "response_parse", False, "failed", False),
        ("daily", "SHOP_SESSION_VALIDATION_FAILED", "session_preparation", False, "failed", False),
        ("daily", "SHOP_SESSION_VALIDATION_FAILED", "session_preparation", True, "paused_reauthorization", False),
    ],
)
def test_session_recovery_eligibility_keeps_the_existing_failure_whitelist(
    kind, code, stage, retryable, status, allowed,
) -> None:
    state = _collection_state(
        collection_item_id=uuid4(), failure_code=code, failure_stage=stage,
        retryable=retryable, status=status, attempt_count=3,
    )
    assert _is_session_recovery_failure(state, job_kind=kind) is allowed


def test_valid_session_label_is_not_fresh_validation_and_never_requests_relogin() -> None:
    now = datetime(2026, 10, 17, 3, tzinfo=UTC)
    item = _collection_state(
        collection_item_id=uuid4(), failure_code="SHOP_SESSION_VALIDATION_FAILED",
        failure_stage="session_preparation", retryable=True, attempt_count=3,
        updated_at=now - timedelta(days=2),
    )
    shop = DashboardShop(item.shop_id, "synthetic recovery shop", ShopPlatform.DOUYIN, True)
    context = SessionRecoveryMetadata(
        shop.shop_id, 3, ShopSessionStatus.VALID,
        now - timedelta(days=1), now - timedelta(minutes=34), True,
    )
    params = dict(
        item=item, job_kind="daily", shop=shop, context=context, history=[item],
        metric=None, already_used=False, now=now, freshness_seconds=300,
        expected_version=3,
    )
    reason = _session_recovery_block_reason(**params)
    assert reason == "当前有效会话需要服务器复核后才能恢复，无需重复登录"
    assert _session_recovery_requires_validation(context, now=now, freshness_seconds=300)
    # A read can describe the necessary explicit action; this does not enqueue,
    # validate, or change the original strict submission contract.
    assert _session_recovery_block_reason(**params, require_fresh_validation=False) is None
    params["context"] = replace(context, validated_at=now - timedelta(seconds=1))
    assert _session_recovery_block_reason(**params) is None
    params["already_used"] = True
    assert _session_recovery_block_reason(**params) == "该日期已执行过一次会话恢复，请查看最近结果"
    assert item.attempt_count == 3 and item.status == "failed"


def test_recovery_projection_matches_eight_exhausted_daily_items_without_writes_or_validation() -> None:
    """Production-shaped metadata, synthetic shops/IDs; no real credentials/DB."""
    now = datetime(2026, 10, 17, 3, 10, tzinfo=UTC)
    shops = [DashboardShop(uuid4(), f"synthetic recovery {n}", ShopPlatform.DOUYIN, True) for n in (1, 2)]
    states = []
    for shop, day_count in zip(shops, (2, 6), strict=True):
        for offset in range(day_count):
            business_date = date(2026, 10, 10) + timedelta(days=offset)
            failure_time = datetime.combine(business_date + timedelta(days=1), time(hour=1), tzinfo=UTC)
            states.append(replace(_collection_state(
                collection_item_id=uuid4(), failure_code="SHOP_SESSION_VALIDATION_FAILED",
                failure_stage="session_preparation", retryable=True,
                attempt_count=3, updated_at=failure_time,
            ), shop_id=shop.shop_id, business_date=business_date))
    contexts = {shop.shop_id: SessionRecoveryMetadata(
        shop.shop_id, n, ShopSessionStatus.VALID,
        now - timedelta(hours=3), now - timedelta(minutes=34), True,
    ) for n, shop in enumerate(shops, start=2)}
    queries = []

    class ReadOnlyRepository:
        def list_session_recovery_metadata(self, shop_ids):
            queries.append(("metadata", set(shop_ids)))
            return contexts

        def used_session_recovery_items(self, item_ids):
            queries.append(("dedupe", set(item_ids)))
            return set()

    service = OperatingDashboardService(None, repository=ReadOnlyRepository(), settings=Settings(
        _env_file=None, operating_dashboard_collection_execution_enabled=True,
    ))
    coverage = service._coverage(
        shops=shops, metric_by_shop_date={}, collection_states=states,
        range_value=OperatingDashboardDateRangeRead(start_date=date(2026, 10, 10), end_date=date(2026, 10, 15)),
    )
    service._attach_session_recovery_hints(
        coverage, shops=shops, collection_states=states, metric_by_shop_date={}, now=now,
    )
    hints = [sample.session_recovery for sample in coverage.missing_samples if sample.session_recovery]
    assert len(hints) == 8 and all(hint.requires_validation for hint in hints)
    assert queries == [
        ("metadata", {shop.shop_id for shop in shops}),
        ("dedupe", {state.collection_item_id for state in states}),
    ]
    assert all(state.status == "failed" and state.attempt_count == 3 for state in states)
    assert coverage.collected_shop_days == 0


def test_explicit_response_parse_recovery_is_bounded_without_uuid_allowlist() -> None:
    now = datetime(2026, 9, 24, 3, tzinfo=UTC)
    service = OperatingDashboardService(
        None,  # type: ignore[arg-type]
        settings=Settings(
            _env_file=None,
            operating_dashboard_collection_max_attempts=3,
            operating_dashboard_gap_recovery_retry_cooldown_seconds=60,
        ),
    )
    parser_failure = _collection_state(
        collection_item_id=uuid4(),
        updated_at=now - timedelta(minutes=2),
    )

    # Normal gap fill leaves a terminal parser result alone. The explicit
    # recollect path may retry the exact known parser shape without requiring
    # an engineer-maintained item UUID list.
    assert service._manual_gap_recovery_allowed([parser_failure], now=now) is False
    assert (
        service._manual_gap_recovery_allowed(
            [parser_failure],
            now=now,
            allow_response_parse_recovery=True,
        )
        is True
    )
    assert (
        service._manual_gap_recovery_allowed(
            [
                _collection_state(
                    collection_item_id=uuid4(),
                    failure_code="DOUYIN_OPERATING_DATA_METRICS_UNAVAILABLE",
                    updated_at=now - timedelta(minutes=2),
                ),
            ],
            now=now,
            allow_response_parse_recovery=True,
        )
        is False
    )
    assert (
        service._manual_gap_recovery_allowed(
            [
                parser_failure,
                _collection_state(
                    collection_item_id=uuid4(),
                    updated_at=now - timedelta(minutes=1),
                    attempt_count=2,
                ),
            ],
            now=now,
            allow_response_parse_recovery=True,
        )
        is False
    )


def test_only_yesterday_waits_for_the_shanghai_daily_collection_boundary() -> None:
    before_due = datetime(2026, 9, 24, 0, 59, tzinfo=UTC)
    yesterday = date(2026, 9, 23)

    assert operating_collection_wait_until(
        business_date=yesterday,
        now=before_due,
        local_time=time(hour=9),
    ) == datetime(2026, 9, 24, 1, tzinfo=UTC)
    assert (
        operating_collection_wait_until(
            business_date=date(2026, 9, 22),
            now=before_due,
            local_time=time(hour=9),
        )
        is None
    )
    assert (
        operating_collection_wait_until(
            business_date=yesterday,
            now=datetime(2026, 9, 24, 1, tzinfo=UTC),
            local_time=time(hour=9),
        )
        is None
    )


def test_coverage_marks_a_delayed_yesterday_item_as_waiting_for_collection_time() -> None:
    state = _collection_state(
        collection_item_id=uuid4(),
        status=OperatingCollectionItemStatus.PENDING.value,
        failure_code=COLLECTION_WAITING_FOR_DAILY_BOUNDARY,
        failure_stage="queued",
    )
    service = _recovery_service()
    coverage = service._coverage(
        shops=[
            DashboardShop(
                state.shop_id,
                "等待采集时间店铺",
                ShopPlatform.DOUYIN,
                True,
            ),
        ],
        metric_by_shop_date={},
        collection_states=[state],
        range_value=OperatingDashboardDateRangeRead(
            start_date=state.business_date,
            end_date=state.business_date,
        ),
    )

    assert coverage.missing_samples[0].state == "waiting_collection_time"
    assert coverage.missing_samples[0].failure_reason == "等待每日采集时间后再请求平台"


def test_coverage_maps_failed_state_to_a_safe_reason_from_the_failure_code() -> None:
    state = _collection_state(collection_item_id=uuid4())
    service = _recovery_service()
    coverage = service._coverage(
        shops=[
            DashboardShop(
                state.shop_id,
                "覆盖率失败原因店铺",
                ShopPlatform.DOUYIN,
                True,
            ),
        ],
        metric_by_shop_date={},
        collection_states=[state],
        range_value=OperatingDashboardDateRangeRead(
            start_date=state.business_date,
            end_date=state.business_date,
        ),
    )

    assert coverage.missing_samples[0].state == "failed"
    assert coverage.missing_samples[0].failure_reason == "抖店经营数据响应无效"


@pytest.mark.parametrize(
    ("failure_code", "expected_reason"),
    [
        (
            "DOUYIN_OPERATING_DATA_METRICS_UNAVAILABLE",
            "抖店平台未提供可确认的经营指标值",
        ),
        ("DOUYIN_OPERATING_DATA_METRICS_NOT_READY", "抖店经营指标暂未就绪"),
        ("DOUYIN_OPERATING_DATA_CORE_METRIC_MISSING", "抖店经营数据响应缺少必要指标"),
    ],
)
def test_coverage_maps_known_core_metric_unknown_states_without_reopening_them(
    failure_code: str,
    expected_reason: str,
) -> None:
    state = _collection_state(collection_item_id=uuid4(), failure_code=failure_code)
    service = _recovery_service()
    coverage = service._coverage(
        shops=[
            DashboardShop(
                state.shop_id,
                "平台指标未知店铺",
                ShopPlatform.DOUYIN,
                True,
            ),
        ],
        metric_by_shop_date={},
        collection_states=[state],
        range_value=OperatingDashboardDateRangeRead(
            start_date=state.business_date,
            end_date=state.business_date,
        ),
    )

    assert coverage.missing_samples[0].state == "unknown"
    assert coverage.missing_samples[0].failure_reason == expected_reason
    assert service._manual_gap_recovery_allowed([state], now=state.updated_at) is False


def test_partial_range_keeps_collected_facts_and_marks_coverage_incomplete() -> None:
    first_shop_id = uuid4()
    second_shop_id = uuid4()
    first_day = date(2026, 9, 18)
    second_day = date(2026, 9, 19)
    shops = [
        DashboardShop(first_shop_id, "部分覆盖店铺", ShopPlatform.DOUYIN, True),
        DashboardShop(second_shop_id, "完整覆盖店铺", ShopPlatform.DOUYIN, True),
    ]
    metrics = {
        (first_shop_id, first_day): _metric(
            shop_id=first_shop_id,
            business_date=first_day,
            turnover_cents=100,
            order_count=1,
        ),
        (second_shop_id, first_day): _metric(
            shop_id=second_shop_id,
            business_date=first_day,
            turnover_cents=200,
            order_count=2,
        ),
        (second_shop_id, second_day): _metric(
            shop_id=second_shop_id,
            business_date=second_day,
            turnover_cents=0,
            order_count=0,
        ),
    }
    selected_range = OperatingDashboardDateRangeRead(
        start_date=first_day,
        end_date=second_day,
    )

    current = OperatingDashboardService._shop_range_values(
        shops,
        metrics,
        selected_range,
    )
    assert current[first_shop_id].turnover_cents == 100
    assert current[first_shop_id].order_count == 1
    assert current[first_shop_id].coverage_complete is False
    assert current[second_shop_id].turnover_cents == 200
    assert current[second_shop_id].order_count == 2
    assert current[second_shop_id].coverage_complete is True

    summary = OperatingDashboardService._summary(
        current,
        current,
        shop_count=2,
        current_core_coverage_complete=False,
        previous_core_coverage_complete=True,
        current_refund_coverage_complete=False,
        previous_refund_coverage_complete=True,
    )
    assert summary.turnover_cents == 300
    assert summary.order_count == 3
    assert summary.turnover_comparison.state == "unavailable"
    assert summary.order_comparison.state == "unavailable"

    trend = OperatingDashboardService._trend(
        object(),  # type: ignore[arg-type]
        shops,
        metrics,
        selected_range,
    )
    assert [(point.turnover_cents, point.order_count) for point in trend] == [
        (300, 3),
        (0, 0),
    ]
    assert [point.coverage_complete for point in trend] == [True, False]


def test_refund_observation_uses_its_own_coverage_and_preserves_zero() -> None:
    shop_id = uuid4()
    first_day = date(2026, 9, 18)
    second_day = date(2026, 9, 19)
    shops = [DashboardShop(shop_id, "退款口径店铺", ShopPlatform.DOUYIN, True)]
    selected_range = OperatingDashboardDateRangeRead(
        start_date=first_day,
        end_date=second_day,
    )
    metrics = {
        (shop_id, first_day): _metric(
            shop_id=shop_id,
            business_date=first_day,
            turnover_cents=100,
            order_count=1,
            refund_order_count=0,
            refund_order_status="available",
        ),
        (shop_id, second_day): _metric(
            shop_id=shop_id,
            business_date=second_day,
            turnover_cents=200,
            order_count=2,
            refund_order_count=None,
            refund_order_status="not_ready",
        ),
    }

    values = OperatingDashboardService._shop_range_values(
        shops,
        metrics,
        selected_range,
    )
    summary = OperatingDashboardService._summary(
        values,
        values,
        shop_count=1,
        current_core_coverage_complete=True,
        previous_core_coverage_complete=True,
        current_refund_coverage_complete=False,
        previous_refund_coverage_complete=False,
    )

    assert values[shop_id].turnover_cents == 300
    assert values[shop_id].order_count == 3
    assert values[shop_id].coverage_complete is True
    assert values[shop_id].refund_order_count == 0
    assert values[shop_id].refund_order_coverage_complete is False
    assert summary.refund_order_count == 0
    assert summary.refund_order_coverage_complete is False
    assert summary.refund_order_comparison.state == "unavailable"


def test_confirmed_zero_core_values_and_positive_refund_remain_independent() -> None:
    """A real zero is not a missing observation or a proxy for refund data."""

    shop_id = uuid4()
    business_date = date(2026, 9, 18)
    shop = DashboardShop(shop_id, "零成交退款店铺", ShopPlatform.DOUYIN, True)
    metric = _metric(
        shop_id=shop_id,
        business_date=business_date,
        turnover_cents=0,
        order_count=0,
        refund_order_count=3,
        refund_order_status="available",
    )
    range_value = OperatingDashboardDateRangeRead(
        start_date=business_date,
        end_date=business_date,
    )

    values = OperatingDashboardService._shop_range_values(
        [shop],
        {(shop_id, business_date): metric},
        range_value,
    )
    summary = OperatingDashboardService._summary(
        values,
        values,
        shop_count=1,
        current_core_coverage_complete=True,
        previous_core_coverage_complete=True,
        current_refund_coverage_complete=True,
        previous_refund_coverage_complete=True,
    )

    assert values[shop_id].turnover_cents == 0
    assert values[shop_id].order_count == 0
    assert values[shop_id].refund_order_count == 3
    assert values[shop_id].coverage_complete is True
    assert values[shop_id].refund_order_coverage_complete is True
    assert summary.turnover_cents == 0
    assert summary.order_count == 0
    assert summary.refund_order_count == 3


def test_confirmed_operating_start_excludes_only_pre_operation_dates() -> None:
    shop_id = uuid4()
    start = date(2026, 9, 14)
    opening = date(2026, 9, 16)
    end = date(2026, 9, 17)
    shop = DashboardShop(
        shop_id,
        "有明确经营起算日店铺",
        ShopPlatform.DOUYIN,
        True,
        operating_start_date=opening,
    )
    metrics = {
        (shop_id, opening): _metric(
            shop_id=shop_id,
            business_date=opening,
            turnover_cents=0,
            order_count=0,
            refund_order_count=0,
            refund_order_status="available",
        ),
        (shop_id, end): _metric(
            shop_id=shop_id,
            business_date=end,
            turnover_cents=100,
            order_count=1,
            refund_order_count=0,
            refund_order_status="available",
        ),
    }
    range_value = OperatingDashboardDateRangeRead(start_date=start, end_date=end)
    service = _recovery_service()

    coverage = service._coverage(
        shops=[shop],
        metric_by_shop_date=metrics,
        collection_states=[],
        range_value=range_value,
    )
    values = OperatingDashboardService._shop_range_values(
        [shop],
        metrics,
        range_value,
    )
    trend = OperatingDashboardService._trend(
        object(),  # type: ignore[arg-type]
        [shop],
        metrics,
        range_value,
    )

    assert coverage.total_shop_days == 2
    assert coverage.collected_shop_days == 2
    assert coverage.missing_shop_days == 0
    assert coverage.not_operating_shop_days == 2
    assert coverage.no_operating_scope is False
    assert values[shop_id].turnover_cents == 100
    assert values[shop_id].order_count == 1
    assert values[shop_id].coverage_complete is True
    # A date range partly before operation can still display its in-scope
    # facts, but it cannot support a made-up period comparison.
    assert (
        OperatingDashboardService._range_coverage_complete(
            [shop],
            metrics,
            range_value,
        )
        is False
    )
    assert [point.turnover_cents for point in trend] == [None, None, 0, 100]
    assert [point.coverage_complete for point in trend] == [False, False, True, True]


def test_unknown_operating_start_remains_in_full_coverage_denominator() -> None:
    shop = DashboardShop(uuid4(), "起算日未知店铺", ShopPlatform.DOUYIN, True)
    range_value = OperatingDashboardDateRangeRead(
        start_date=date(2026, 9, 14),
        end_date=date(2026, 9, 16),
    )

    coverage = _recovery_service()._coverage(
        shops=[shop],
        metric_by_shop_date={},
        collection_states=[],
        range_value=range_value,
    )

    assert coverage.total_shop_days == 3
    assert coverage.missing_shop_days == 3
    assert coverage.not_operating_shop_days == 0
    assert coverage.shops_with_unknown_operating_start == 1
    assert coverage.no_operating_scope is False


def test_all_dates_before_confirmed_start_are_not_operating_not_missing() -> None:
    shop = DashboardShop(
        uuid4(),
        "尚未经营店铺",
        ShopPlatform.DOUYIN,
        True,
        operating_start_date=date(2026, 9, 20),
    )
    range_value = OperatingDashboardDateRangeRead(
        start_date=date(2026, 9, 14),
        end_date=date(2026, 9, 16),
    )
    service = _recovery_service()

    coverage = service._coverage(
        shops=[shop],
        metric_by_shop_date={},
        collection_states=[],
        range_value=range_value,
    )
    values = OperatingDashboardService._shop_range_values(
        [shop],
        {},
        range_value,
    )

    assert coverage.total_shop_days == 0
    assert coverage.missing_shop_days == 0
    assert coverage.not_operating_shop_days == 3
    assert coverage.no_operating_scope is True
    assert values[shop.shop_id].not_operating_for_range is True
    assert values[shop.shop_id].turnover_cents is None
    assert values[shop.shop_id].coverage_complete is False
    assert values[shop.shop_id].refund_order_coverage_complete is False


def test_legacy_collection_planning_excludes_known_pre_operation_days() -> None:
    """The final planner gate also protects older direct job callers."""

    shop = DashboardShop(
        uuid4(),
        "兼容入队范围店铺",
        ShopPlatform.DOUYIN,
        True,
        operating_start_date=date(2026, 9, 16),
    )
    planned = _prioritized_collection_items(
        shops=[shop],
        start_date=date(2026, 9, 14),
        end_date=date(2026, 9, 17),
        business_dates=None,
        business_dates_by_shop=None,
    )

    assert [business_date for _, business_date in planned] == [
        date(2026, 9, 17),
        date(2026, 9, 16),
    ]

def test_success_ends_failure_chain_without_lifetime_attempt_exhaustion() -> None:
    now = datetime(2026, 9, 24, 3, tzinfo=UTC)
    service = OperatingDashboardService(
        None,  # type: ignore[arg-type]
        settings=Settings(
            _env_file=None,
            operating_dashboard_collection_max_attempts=3,
            operating_dashboard_gap_recovery_retry_cooldown_seconds=60,
        ),
    )
    success = _collection_state(
        collection_item_id=uuid4(),
        status=OperatingCollectionItemStatus.SUCCEEDED.value,
        attempt_count=10,
        updated_at=now - timedelta(minutes=5),
    )
    failure = _collection_state(
        collection_item_id=uuid4(),
        updated_at=now - timedelta(minutes=2),
    )
    assert service._manual_gap_recovery_allowed(
        [success, failure], now=now, allow_response_parse_recovery=True,
    )
    assert not service._manual_gap_recovery_allowed(
        [failure], now=failure.updated_at, allow_response_parse_recovery=True,
    )
