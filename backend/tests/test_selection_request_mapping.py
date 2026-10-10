"""Offline query preparation, not a real request or frozen rolling-date rule."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.modules.product_selection.exceptions import SelectionRequestUnconfirmedError
from app.modules.product_selection.request_mapping import prepare_short_video_scope
from app.modules.product_selection.run_contract import SelectionRunOriginal
from app.modules.product_selection.run_service import (
    resolve_selection_request, selection_request_mapping_available,
)


def _original(**changes):
    return SelectionRunOriginal.model_validate({
        "shop_id": uuid4(), "channel": "short-video", "period": "7d",
        "industry_id": "7", "category_ids": ["1000009092", "1000009142"],
        "brand": "all", "price_mode": "all", "first_listed_only": False,
        "rank_from": 1, "rank_to": 10, **changes,
    })


def test_observed_seven_day_business_parameters_preserve_strings_and_empty_values():
    scope = prepare_short_video_scope(
        _original(), period_begin=date(2026, 10, 3), period_end=date(2026, 10, 9),
    )
    query = {"page_no": "1", "page_size": "10", **scope.model_dump()}
    assert query == {
        "page_no": "1", "page_size": "10", "industry_id": "7",
        "category_id": "1000009092,1000009142", "brand_type": "-1",
        "price_bin": "不限", "search_info": "", "rank_data_type": "1",
        "begin_date": "2026/10/03 00:00:00", "end_date": "2026/10/09 00:00:00",
        "date_type": "21", "activity_id": "",
    }
    assert all(type(value) is str for value in query.values())


def test_preparation_does_not_replace_selected_category_or_supplied_dates_with_sample():
    # Synthetic IDs and a different interval establish no historical defaults.
    original = _original(industry_id="19", category_ids=["9007199254740993123", "12002"])
    scope = prepare_short_video_scope(
        original, period_begin=date(2027, 1, 28), period_end=date(2027, 2, 3),
    )
    assert scope.industry_id == "19"
    assert scope.category_id == "9007199254740993123,12002"
    assert scope.begin_date == "2027/01/28 00:00:00"
    assert scope.end_date == "2027/02/03 00:00:00"


@pytest.mark.parametrize("changes,reason", [
    ({"channel": "baiying"}, "CHANNEL_UNCONFIRMED"),
    ({"period": "realtime"}, "PERIOD_UNCONFIRMED"),
    ({"period": "1d"}, "PERIOD_UNCONFIRMED"),
    ({"period": "30d"}, "PERIOD_UNCONFIRMED"),
    ({"brand": "known"}, "BRAND_UNCONFIRMED"),
    ({"brand": "unknown"}, "BRAND_UNCONFIRMED"),
    ({"price_mode": "custom", "price_above": "0"}, "PRICE_UNCONFIRMED"),
    ({"first_listed_only": True}, "FIRST_LISTED_FILTER_UNCONFIRMED"),
    ({"industry_id": "0"}, "CATEGORY_PATH_UNCONFIRMED"),
    ({"category_ids": ["1000009092", "0"]}, "CATEGORY_PATH_UNCONFIRMED"),
    ({"category_ids": ["1000009092", "1000009092"]}, "CATEGORY_PATH_UNCONFIRMED"),
])
def test_unconfirmed_choices_are_rejected_without_substituting_or_ignoring(changes, reason):
    with pytest.raises(SelectionRequestUnconfirmedError) as caught:
        prepare_short_video_scope(
            _original(**changes), period_begin=date(2026, 10, 3), period_end=date(2026, 10, 9),
        )
    assert caught.value.details == {"reason": reason}


@pytest.mark.parametrize("start,end", [
    (date(2026, 10, 3), date(2026, 10, 3)),
    (date(2026, 10, 9), date(2026, 10, 3)),
    (date(2026, 10, 3), date(2026, 10, 10)),
    (None, date(2026, 10, 9)),
    (datetime(2026, 10, 3, tzinfo=UTC), date(2026, 10, 9)),
])
def test_explicit_interval_is_required_and_must_be_exactly_seven_days(start, end):
    with pytest.raises(SelectionRequestUnconfirmedError) as caught:
        prepare_short_video_scope(_original(), period_begin=start, period_end=end)
    assert caught.value.details == {"reason": "EXPLICIT_PERIOD_UNCONFIRMED"}


@pytest.mark.parametrize("now", [
    datetime(2026, 10, 10, 8, tzinfo=UTC),
    datetime(2026, 10, 11, 8, tzinfo=UTC),
    datetime(2027, 1, 1, 0, tzinfo=UTC),
])
def test_public_resolver_stays_closed_regardless_of_clock_or_capture_date(now):
    assert selection_request_mapping_available() is False
    with pytest.raises(SelectionRequestUnconfirmedError) as caught:
        resolve_selection_request(_original(), now)
    assert caught.value.details == {"reason": "PLATFORM_DATE_WINDOW_UNCONFIRMED"}
