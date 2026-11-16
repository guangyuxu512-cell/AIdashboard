"""Synthetic HTTPX MockTransport/FakeSigner only, never a live request."""

import json
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

from app.modules.product_data.source import ProductDataSlice
from app.platforms.douyin.api_client import DouyinApiClient
from app.platforms.douyin.product_data import CompassProductDataBusinessError
from app.platforms.douyin.product_data_connector import DouyinProductDataConnector
from app.platforms.exceptions import PlatformAuthenticationInvalidError, PlatformIdentityMismatchError
from tests.test_douyin_product_data import payload, current, SHOP
from tests.test_selection_connector import _context, FakeSigner


def scope(context):
    return ProductDataSlice(shop_id=context.shop_id, period="7d", start_date="2026-01-01", end_date="2026-01-07")


def test_fixed_product_endpoint_exact_numbers_current_cookie_and_query(caplog):
    context, signer = _context(), FakeSigner()
    frozen = scope(context)
    raw = payload()
    current(raw, "pay_refund_ratio")["value"] = "exact-decimal"
    current(raw, "pay_cnt")["value"] = 900719925474099312345
    encoded = json.dumps(raw).replace('"exact-decimal"', "0.103846080868261780123456789")
    seen = []

    def handle(request):
        seen.append(request)
        assert request.url.host == "compass.jinritemai.com"
        assert request.url.path == "/compass_api/shop/product/product/product_list"
        assert signer.requests[-1].cookie.get_secret_value() == request.headers["cookie"]
        for key, value in frozen.business_query(1).items():
            assert request.url.params[key] == value
        assert request.url.params["fp"] == "synthetic-current-fingerprint"
        assert request.url.params["verifyFp"] == request.url.params["fp"]
        assert request.url.params["a_bogus"] == "synthetic-new"
        return httpx.Response(200, text=encoded, headers={"set-cookie": "sessionid=synthetic-rotated; Path=/; Secure"})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = DouyinProductDataConnector(DouyinApiClient(client, signer=signer)).page(context, frozen, SHOP, 1)
    row = result.page.products[0]
    assert row.metric("pay_refund_ratio").raw_value == Decimal("0.103846080868261780123456789")
    assert row.metric("pay_cnt").raw_value == Decimal(900719925474099312345)
    assert row.metric("pay_refund_ratio").display_value == row.metric("pay_refund_ratio").raw_value
    assert result.cookie_updates[0].value.get_secret_value() == "synthetic-rotated"
    assert len(seen) == len(signer.requests) == 1
    assert "synthetic-current-fingerprint" not in caplog.text
    assert "synthetic-rotated" not in caplog.text


@pytest.mark.parametrize("status", [401, 403])
def test_only_explicit_http_auth_is_auth_invalid(status):
    context = _context()
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status))) as client:
        with pytest.raises(PlatformAuthenticationInvalidError):
            DouyinProductDataConnector(DouyinApiClient(client, signer=FakeSigner())).page(context, scope(context), SHOP, 1)


def test_business_rejection_is_not_auth_invalid_and_does_not_expose_msg():
    context = _context()
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"st": 100008, "msg": "must-not-leak"}))) as client:
        with pytest.raises(CompassProductDataBusinessError) as error:
            DouyinProductDataConnector(DouyinApiClient(client, signer=FakeSigner())).page(context, scope(context), SHOP, 1)
    assert error.value.code == "DOUYIN_PRODUCT_DATA_REJECTED"
    assert "must-not-leak" not in str(error.value) + repr(error.value.details)


def test_wrong_shop_context_rejected_before_signer_and_http():
    context, signer = _context(), FakeSigner()
    frozen = scope(context).model_copy(update={"shop_id": uuid4()})
    with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("must not call HTTP"))) as client:
        with pytest.raises(PlatformIdentityMismatchError):
            DouyinProductDataConnector(DouyinApiClient(client, signer=signer)).page(context, frozen, SHOP, 1)
    assert signer.requests == []
