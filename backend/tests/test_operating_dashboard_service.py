from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.modules.operating_dashboard.exceptions import (
    OperatingDashboardInvalidRequestError,
)
from app.modules.operating_dashboard.service import OperatingDashboardService


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
