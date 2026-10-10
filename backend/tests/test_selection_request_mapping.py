"""Offline query preparation, not a real request or frozen rolling-date rule."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.modules.product_selection.exceptions import SelectionRequestUnconfirmedError
from app.modules.product_selection.request_mapping import prepare_short_video_scope, freeze_short_video_request, validate_shop_category
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
    ({"category_ids": ["7", "1000009092", "1000009142"]}, "CATEGORY_PATH_UNCONFIRMED"),
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


@pytest.mark.parametrize("now,primary,backup", [
    (datetime(2026, 10, 10, 16, tzinfo=UTC), "2026/10/04 00:00:00", "2026/10/03 00:00:00"),
    (datetime(2026, 10, 31, 16, tzinfo=UTC), "2026/10/25 00:00:00", "2026/10/24 00:00:00"),
    (datetime(2026, 12, 31, 16, tzinfo=UTC), "2026/12/25 00:00:00", "2026/12/24 00:00:00"),
])
def test_public_resolver_freezes_user_approved_shanghai_windows(now, primary, backup):
    assert selection_request_mapping_available() is True
    request = resolve_selection_request(_original(), now)
    assert request.version == 2 and request.date_outcome is None
    assert request.scope.begin_date == primary
    assert request.date_plan.backup_scope.begin_date == backup
    assert (request.scope.period_end - request.scope.period_begin).days == 6
    assert request.page_numbers == (1,)


def test_fingerprint_excludes_outcome_but_keeps_frozen_plan_and_legacy_bytes():
    from app.modules.product_selection.run_contract import SelectionResolvedRequest, SelectionDateOutcome
    from hashlib import sha256
    import json
    request = freeze_short_video_request(_original(rank_from=11, rank_to=20), datetime.now(UTC))
    assert request.page_numbers == (1, 2)
    assert request.model_copy(update={"date_outcome": SelectionDateOutcome(state="backup")}).fingerprint() == request.fingerprint()
    legacy = SelectionResolvedRequest(original=request.original, scope=request.scope, page_numbers=(2,))
    old = legacy.model_dump(mode="json", exclude={"date_plan", "date_outcome"})
    assert legacy.fingerprint() == sha256(json.dumps(old, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    with pytest.raises(ValueError): request.actual_scope()
    with pytest.raises(SelectionRequestUnconfirmedError):
        freeze_short_video_request(_original(rank_to=21), datetime.now(UTC))


@pytest.mark.parametrize("industry_wrapped", [False, True])
def test_category_membership_is_current_shop_industry_and_ordered_path_not_leaf_only(industry_wrapped):
    from app.modules.product_selection.schemas import SelectionCategoriesRead
    original = _original()
    nodes = [{"category_id": "1000009092", "name": "父级", "children": [{"category_id": "1000009142", "name": "子级", "children": []}]}]
    if industry_wrapped:
        nodes = [{"category_id": "5", "name": "其它行业", "children": [{"category_id": "5001", "name": "其它类目", "children": []}]},
            {"category_id": "7", "name": "示例行业", "children": nodes}]
    tree = SelectionCategoriesRead(shop_id=original.shop_id, industry_id="7", industry_name="示例行业", selected_category_id=None,
        nodes=nodes)
    validate_shop_category(original, tree)
    validate_shop_category(original.model_copy(update={"category_ids": ("1000009092",)}), tree)
    with pytest.raises(SelectionRequestUnconfirmedError):
        validate_shop_category(original.model_copy(update={"shop_id": uuid4()}), tree)
    with pytest.raises(SelectionRequestUnconfirmedError):
        validate_shop_category(original.model_copy(update={"category_ids": ("1000009142", "1000009092")}), tree)
    for category_ids in [("7",), ("7", "1000009092", "1000009142"), ("1000009142",), ("1000009092", "0"), ("5", "5001"), ("5001",)]:
        with pytest.raises(SelectionRequestUnconfirmedError):
            validate_shop_category(original.model_copy(update={"category_ids": category_ids}), tree)
    with pytest.raises(SelectionRequestUnconfirmedError):
        validate_shop_category(original.model_copy(update={"industry_id": "5", "category_ids": ("5001",)}), tree)
