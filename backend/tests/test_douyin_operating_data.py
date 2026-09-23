from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.integrations.douyin_signer import DouyinSignResult
from app.modules.sessions.auth_context import ShopSessionAuthContext, StoredSessionCookie
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.api_client import DouyinApiClient
from app.platforms.douyin.operating_data import (
    DouyinOperatingDataBusinessError,
    DouyinOperatingDataConnector,
    build_core_index_query,
    parse_core_index_metrics,
    previous_completed_shanghai_date,
)
from app.platforms.exceptions import PlatformResponseInvalidError


STATISTIC_DATE = date(2026, 9, 19)


class FakeSigner:
    def __init__(self) -> None:
        self.requests = []

    def sign(self, request):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        return DouyinSignResult(
            ok=True,
            a_bogus=SecretStr("synthetic-a-bogus"),
            duration_ms=1,
        )


def _auth_context() -> ShopSessionAuthContext:
    return ShopSessionAuthContext(
        shop_id=uuid4(),
        platform=ShopPlatform.DOUYIN,
        session_version=1,
        cookies=(
            StoredSessionCookie(
                name="sessionid",
                value=SecretStr("synthetic-cookie"),
                domain=".jinritemai.com",
                path="/",
                secure=True,
            ),
        ),
    )


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


def test_core_index_signed_request_uses_unsigned_context_then_injects_signature() -> None:
    signer = FakeSigner()
    auth_context = _auth_context()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.host == "compass.jinritemai.com"
        assert request.url.path == "/compass_api/shop/common/homepage/core_index_v3"
        assert request.url.params["a_bogus"] == "synthetic-a-bogus"
        assert request.url.params["begin_date"] == "2026/09/19 00:00:00"
        assert request.url.params["end_date"] == "2026/09/19 00:00:00"
        assert request.url.params["date_type"] == "999"
        assert request.url.params["_lid"] == "synthetic-per-request-lid"
        assert "verifyFp" not in request.url.params
        assert "fp" not in request.url.params
        assert "msToken" not in request.url.params
        assert request.headers["referer"] == "https://compass.jinritemai.com/shop"
        assert request.headers["x-e2e-platform"] == "compass"
        assert "origin" not in request.headers
        return httpx.Response(200, request=request, json=_payload())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        read = DouyinOperatingDataConnector(
            api_client=DouyinApiClient(client, signer=signer),
        ).fetch_daily_metrics(
            auth_context.shop_id,
            auth_context,
            STATISTIC_DATE,
            request_lid="synthetic-per-request-lid",
        )

    assert len(signer.requests) == 1
    sign_request = signer.requests[0]
    assert sign_request.host == "compass.jinritemai.com"
    assert sign_request.aid is None
    assert sign_request.page_id is None
    assert "a_bogus" not in (sign_request.full_url or "")
    assert read.metrics.income_amt_cents == 98660
    assert read.metrics.income_amt_yuan == Decimal("986.60")
    assert read.metrics.pay_cnt == 93
    assert read.signature_duration_ms is not None
    assert read.platform_duration_ms >= 0
    assert read.parse_duration_ms >= 0


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


def test_core_index_parser_keeps_null_as_missing_and_rejects_business_or_core_shape_errors() -> None:
    payload = _payload()
    card = payload["data"]["module_data"]["homepage_core_index"][
        "compass_general_multi_index_card_value"
    ]["data"][0]
    card["income_amt"] = _metric(None)

    metrics = parse_core_index_metrics(payload)

    assert metrics.income_amt_cents is None
    assert metrics.income_amt_yuan is None

    with pytest.raises(DouyinOperatingDataBusinessError):
        parse_core_index_metrics(_payload(status=100008))

    broken = _payload()
    broken_card = broken["data"]["module_data"]["homepage_core_index"][
        "compass_general_multi_index_card_value"
    ]["data"][0]
    broken_card.pop("pay_cnt")
    with pytest.raises(PlatformResponseInvalidError):
        parse_core_index_metrics(broken)


def test_core_index_parser_does_not_require_unpersisted_card_metrics() -> None:
    """A real successful Compass card can omit refund/settlement candidates."""

    payload = _payload()
    card = payload["data"]["module_data"]["homepage_core_index"][
        "compass_general_multi_index_card_value"
    ]["data"][0]
    card["rfndsuc_amt_pay_time"] = {"index_value": {"value": {}}}
    card["refund_order_cnt"] = {"unexpected": "shape"}

    metrics = parse_core_index_metrics(payload)

    assert metrics.income_amt_cents == 98660
    assert metrics.pay_cnt == 93
