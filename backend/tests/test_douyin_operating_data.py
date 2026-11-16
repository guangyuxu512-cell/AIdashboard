from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.platforms.douyin.operating_data import (
    DouyinOperatingDataBusinessError,
    DouyinOperatingDataMetricMissingError,
    DouyinOperatingDataMetricNotReadyError,
    DouyinOperatingDataMetricUnavailableError,
    build_core_index_query,
    parse_core_index_metrics,
    previous_completed_shanghai_date,
)
from app.platforms.exceptions import PlatformResponseInvalidError


STATISTIC_DATE = date(2026, 9, 19)


def _metric(value: int | str | None) -> dict[str, object]:
    return {"index_value": {"value": {"value": value}}}


def _payload(*, status: int | str = 0) -> dict[str, object]:
    return {
        "st": status,
        "data": {
            "module_data": {
                "homepage_core_index": {
                    "compass_general_multi_index_card_value": {
                        "data": [
                            {
                                "income_amt": _metric(98660),
                                "pay_cnt": _metric(93),
                            },
                        ],
                    },
                },
            },
        },
    }


def test_core_index_query_never_invents_or_persists_lid() -> None:
    query = build_core_index_query(STATISTIC_DATE, request_lid="  ")

    assert "_lid" not in query
    assert "a_bogus" not in query
    assert query["index_selected"].startswith("income_amt,pay_amt")


def test_previous_completed_date_uses_asia_shanghai_calendar() -> None:
    assert previous_completed_shanghai_date(
        datetime(2026, 9, 20, 16, 1, tzinfo=UTC),
    ) == date(2026, 9, 20)
    assert previous_completed_shanghai_date(
        datetime(2026, 9, 20, 15, 59, tzinfo=UTC),
    ) == date(2026, 9, 19)


def test_core_index_parser_classifies_unknown_required_metric_states_without_fabricating_zero() -> None:
    payload = _payload()
    card = payload["data"]["module_data"]["homepage_core_index"][
        "compass_general_multi_index_card_value"
    ]["data"][0]
    card["income_amt"] = _metric(None)

    with pytest.raises(DouyinOperatingDataMetricNotReadyError) as not_ready:
        parse_core_index_metrics(payload)
    assert not_ready.value.code == "DOUYIN_OPERATING_DATA_METRICS_NOT_READY"

    unit_only = _payload()
    unit_only_card = unit_only["data"]["module_data"]["homepage_core_index"][
        "compass_general_multi_index_card_value"
    ]["data"][0]
    # This exact value-container shape came from the controlled, redacted
    # production response.  It identifies neither zero activity nor a Shop
    # lifecycle boundary because no scalar value was supplied.
    unit_only_card["income_amt"] = {"index_value": {"value": {"unit": "元"}}}
    with pytest.raises(DouyinOperatingDataMetricUnavailableError) as unavailable:
        parse_core_index_metrics(unit_only)
    assert unavailable.value.code == "DOUYIN_OPERATING_DATA_METRICS_UNAVAILABLE"

    with pytest.raises(DouyinOperatingDataBusinessError) as rejected:
        parse_core_index_metrics(_payload(status=100008))
    # The connector preserves only the safe platform status.  It must not
    # invent a "not ready" meaning for a non-success business response.
    assert rejected.value.code == "DOUYIN_OPERATING_DATA_REJECTED"
    assert rejected.value.details == {"platform_code": "100008"}

    broken = _payload()
    broken_card = broken["data"]["module_data"]["homepage_core_index"][
        "compass_general_multi_index_card_value"
    ]["data"][0]
    broken_card.pop("pay_cnt")
    with pytest.raises(DouyinOperatingDataMetricMissingError) as missing:
        parse_core_index_metrics(broken)
    assert missing.value.code == "DOUYIN_OPERATING_DATA_CORE_METRIC_MISSING"

    malformed = _payload()
    malformed_card = malformed["data"]["module_data"]["homepage_core_index"][
        "compass_general_multi_index_card_value"
    ]["data"][0]
    malformed_card["pay_cnt"] = {"index_value": {"value": {"unexpected": "shape"}}}
    with pytest.raises(PlatformResponseInvalidError) as invalid:
        parse_core_index_metrics(malformed)
    assert type(invalid.value) is PlatformResponseInvalidError


def test_core_index_parser_preserves_explicit_zero_core_values() -> None:
    payload = _payload()
    card = payload["data"]["module_data"]["homepage_core_index"][
        "compass_general_multi_index_card_value"
    ]["data"][0]
    card["income_amt"] = _metric(0)
    card["pay_cnt"] = _metric(0)

    metrics = parse_core_index_metrics(payload)

    assert metrics.income_amt_cents == 0
    assert metrics.income_amt_yuan == Decimal("0")
    assert metrics.pay_cnt == 0


def test_core_index_parser_does_not_require_unpersisted_card_metrics() -> None:
    """A bad optional refund card cannot invalidate the confirmed core facts."""

    payload = _payload()
    card = payload["data"]["module_data"]["homepage_core_index"][
        "compass_general_multi_index_card_value"
    ]["data"][0]
    card["rfndsuc_amt_pay_time"] = {"index_value": {"value": {}}}
    card["refund_order_cnt"] = {"unexpected": "shape"}

    metrics = parse_core_index_metrics(payload)

    assert metrics.income_amt_cents == 98660
    assert metrics.pay_cnt == 93
    assert metrics.refund_order_count is None
    assert metrics.refund_order_status == "invalid"


def test_core_index_parser_reads_only_verified_refund_time_order_count() -> None:
    payload = _payload()
    card = payload["data"]["module_data"]["homepage_core_index"][
        "compass_general_multi_index_card_value"
    ]["data"][0]
    card["refund_order_cnt"] = _metric(9)
    # This is the distinct payment-time metric and deliberately must not be
    # persisted or substituted for the refund-time dashboard value.
    card["refund_order_cnt_pay_time"] = _metric(5)

    metrics = parse_core_index_metrics(payload)

    assert metrics.refund_order_count == 9
    assert metrics.refund_order_status == "available"


@pytest.mark.parametrize(
    ("refund_metric", "expected_status"),
    [
        (None, "unavailable"),
        (_metric(None), "not_ready"),
        ({"unexpected": "shape"}, "invalid"),
        (_metric(-1), "invalid"),
    ],
)
def test_core_index_parser_classifies_optional_refund_observation_without_failing_core(
    refund_metric: dict[str, object] | None,
    expected_status: str,
) -> None:
    payload = _payload()
    card = payload["data"]["module_data"]["homepage_core_index"][
        "compass_general_multi_index_card_value"
    ]["data"][0]
    if refund_metric is not None:
        card["refund_order_cnt"] = refund_metric

    metrics = parse_core_index_metrics(payload)

    assert metrics.income_amt_cents == 98660
    assert metrics.pay_cnt == 93
    assert metrics.refund_order_count is None
    assert metrics.refund_order_status == expected_status
