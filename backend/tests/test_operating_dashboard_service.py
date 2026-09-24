from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.modules.operating_dashboard.enums import OperatingCollectionItemStatus
from app.modules.operating_dashboard.exceptions import (
    OperatingDashboardInvalidRequestError,
)
from app.modules.operating_dashboard.models import ShopOperatingDailyMetric
from app.modules.operating_dashboard.repository import CollectionItemState, DashboardShop
from app.modules.operating_dashboard.schemas import OperatingDashboardDateRangeRead
from app.modules.operating_dashboard.service import OperatingDashboardService
from app.modules.shops.enums import ShopPlatform


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
    updated_at: datetime = datetime(2026, 9, 23, tzinfo=UTC),
) -> CollectionItemState:
    return CollectionItemState(
        collection_item_id=collection_item_id,
        collection_job_id=uuid4(),
        shop_id=uuid4(),
        business_date=date(2026, 9, 22),
        status=OperatingCollectionItemStatus.FAILED.value,
        retryable=retryable,
        attempt_count=attempt_count,
        failure_code=failure_code,
        failure_stage=failure_stage,
        finished_at=updated_at,
        updated_at=updated_at,
        job_kind="daily",
        requested_by_user_id=None,
    )


def _recovery_service(*, approved_item_ids: frozenset[UUID]) -> OperatingDashboardService:
    return OperatingDashboardService(
        None,  # type: ignore[arg-type]
        settings=Settings(
            _env_file=None,
            operating_dashboard_legacy_response_parse_recovery_item_ids=approved_item_ids,
        ),
    )


def test_legacy_response_parse_recovery_allowlist_uses_json_uuid_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item_id = uuid4()
    monkeypatch.setenv(
        "BACKEND_OPERATING_DASHBOARD_LEGACY_RESPONSE_PARSE_RECOVERY_ITEM_IDS",
        f'["{item_id}"]',
    )

    assert (
        Settings(_env_file=None).operating_dashboard_legacy_response_parse_recovery_item_ids
        == frozenset({item_id})
    )


def test_legacy_response_parse_recovery_requires_exact_approved_original_item() -> None:
    now = datetime(2026, 9, 24, tzinfo=UTC)
    approved_item_id = uuid4()
    service = _recovery_service(approved_item_ids=frozenset({approved_item_id}))
    approved = _collection_state(collection_item_id=approved_item_id)

    assert service._automatic_gap_recovery_allowed([approved], now=now) is True
    assert service._manual_gap_recovery_allowed([approved], now=now) is True

    # A generic parse failure remains terminal unless its original UUID was
    # independently approved at Release Gate.
    assert (
        service._automatic_gap_recovery_allowed(
            [_collection_state(collection_item_id=uuid4())],
            now=now,
        )
        is False
    )
    # Even an approved UUID cannot override another stage, the normal
    # cooldown for a retryable item, or an already-retried old item.
    assert (
        service._manual_gap_recovery_allowed(
            [
                _collection_state(
                    collection_item_id=approved_item_id,
                    failure_stage="platform_response",
                ),
            ],
            now=now,
        )
        is False
    )
    assert (
        service._manual_gap_recovery_allowed(
            [
                _collection_state(
                    collection_item_id=approved_item_id,
                    retryable=True,
                    updated_at=now,
                ),
            ],
            now=now,
        )
        is False
    )
    assert (
        service._automatic_gap_recovery_allowed(
            [
                _collection_state(
                    collection_item_id=approved_item_id,
                    attempt_count=2,
                ),
            ],
            now=now,
        )
        is False
    )


def test_legacy_response_parse_allowlist_does_not_reopen_a_later_failure() -> None:
    now = datetime(2026, 9, 24, tzinfo=UTC)
    approved_item_id = uuid4()
    service = _recovery_service(approved_item_ids=frozenset({approved_item_id}))
    original = _collection_state(
        collection_item_id=approved_item_id,
        updated_at=now - timedelta(hours=2),
    )
    later_failure = _collection_state(
        collection_item_id=uuid4(),
        updated_at=now - timedelta(hours=1),
    )

    assert service._automatic_gap_recovery_allowed([original, later_failure], now=now) is False
    assert service._manual_gap_recovery_allowed([original, later_failure], now=now) is False


def test_coverage_maps_failed_state_to_a_safe_reason_from_the_failure_code() -> None:
    state = _collection_state(collection_item_id=uuid4())
    service = _recovery_service(approved_item_ids=frozenset())
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
