from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.product_selection.strategy_contract import SelectionStrategyConditions, SelectionStrategySchedule, SelectionStrategyToggle


def test_strategy_config_is_relative_and_rejects_unregistered_fields():
    request = {"channel": "short-video", "period": "7d", "industry_id": "7", "category_ids": ["1001"], "brand": "all", "price_mode": "all", "rank_from": 1, "rank_to": 30}
    assert SelectionStrategyConditions(request=request).original(uuid4()).period == "7d"
    for field, value in [("begin_date", "2026/10/13 00:00:00"), ("shop_id", str(uuid4())), ("url", "https://example.invalid")]:
        with pytest.raises(ValidationError): SelectionStrategyConditions(request=request | {field: value})
    with pytest.raises(ValidationError): SelectionStrategyConditions(request=request | {"first_listed_only": 0})


@pytest.mark.parametrize("version", [True, False, 0, -1, 1.0, "1"])
def test_strategy_cas_version_is_a_positive_json_integer(version):
    with pytest.raises(ValidationError): SelectionStrategyToggle(enabled=True, expected_version=version)


def test_saved_schedule_config_has_one_explicit_timezone_and_valid_time():
    assert SelectionStrategySchedule(scheduled=True, kind="hourly").timezone == "Asia/Shanghai"
    with pytest.raises(ValidationError): SelectionStrategySchedule(kind="daily", daily_time="24:00")
    with pytest.raises(ValidationError): SelectionStrategySchedule(timezone="UTC")
