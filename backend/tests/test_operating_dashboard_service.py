from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.modules.operating_dashboard.exceptions import (
    OperatingDashboardInvalidRequestError,
)
from app.modules.operating_dashboard.models import ShopOperatingDailyMetric
from app.modules.operating_dashboard.repository import DashboardShop
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
) -> ShopOperatingDailyMetric:
    return ShopOperatingDailyMetric(
        shop_id=shop_id,
        business_date=business_date,
        source_code="douyin_compass_core_index_v3",
        metric_contract="douyin_compass_daily_v1",
        turnover_cents=turnover_cents,
        order_count=order_count,
        collected_at=datetime(2026, 9, 20, tzinfo=UTC),
    )


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
        current_coverage_complete=False,
        previous_coverage_complete=True,
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
