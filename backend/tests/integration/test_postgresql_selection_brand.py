"""Brand persistence and exact connector queries; assigned PG, synthetic I/O."""

import pytest
from sqlalchemy.orm import Session

from app.modules.product_selection.api import get_selection_run_service
from app.modules.product_selection.run_service import SelectionRunService
from app.modules.product_selection.run_contract import SelectionRunReceipt
from app.modules.product_selection.platform_io import SelectionStoredSessionIO
from app.platforms.douyin.product_selection import CompassRankPage, CompassSelectionBusinessError
from tests.integration.test_postgresql_product_selection import selection_context, _product, _api_client
from tests.integration.test_postgresql_selection_runs import _input, _get, _executor, SETTINGS
from tests.integration.test_postgresql_selection_windows import _submit, WindowPlatform, _category_tree
from tests.integration.test_postgresql_selection_strategies import _save

pytestmark = pytest.mark.integration


def _branded(context, brand="known", price=False, **changes):
    prices = {"price_mode": "custom", "price_above": "20", "price_below": "100"} if price else {}
    return _input(context, **({"brand": brand, "rank_from": 1, "rank_to": 11} | prices | changes))


@pytest.mark.parametrize("brand,code", [("known", "1"), ("unknown", "0")])
@pytest.mark.parametrize("price", [False, True])
def test_formal_brand_save_read_post_pages_source_and_repeat(selection_context, brand, code, price):
    context, queries = selection_context, []
    command = _branded(context, brand, price)
    saved = _save(context, conditions={"version": 1, "request": command.original().model_dump(mode="json", exclude={"shop_id"})})
    command = _branded(context, brand, price, strategy_id=saved.strategy_id, strategy_version=saved.version)
    def dependency():
        with Session(context[0]) as session:
            def categories(actor, shop_id):
                assert not session.in_transaction()
                return _category_tree(shop_id)
            yield SelectionRunService(session, settings=SETTINGS, category_reader=categories)
    with _api_client(context) as client:
        client.app.dependency_overrides[get_selection_run_service] = dependency
        headers = {"X-Team-ID": str(context[1][0])}
        assert client.get(f"/api/v1/product-selection/strategies/{saved.strategy_id}", headers=headers).json()["conditions"]["request"]["brand"] == brand
        response = client.post("/api/v1/product-selection/runs", headers=headers, json=command.model_dump(mode="json"))
        assert response.status_code == 202
        assert client.post("/api/v1/product-selection/runs", headers=headers, json=command.model_dump(mode="json")).json() == response.json()
        receipt = SelectionRunReceipt.model_validate(response.json())
    class Connector:
        def rank(self, auth_context, query):
            queries.append(query)
            page = int(query["page_no"])
            return CompassRankPage((_product(f"90000000000000000{page:02}", rank=1 if page == 1 else 11),), page, 10, 11)
    class Platform(WindowPlatform):
        def rank(self, auth_context, request, page_no):
            return SelectionStoredSessionIO(lambda: None, connector=Connector()).rank(auth_context, request, page_no)
    _executor(context, Platform(receipt.execution.request_conditions, {})).execute_available()
    run = _get(context, receipt)
    assert run.status == "succeeded" and run.request_conditions.version == 9 and run.saved_count == 2
    assert [query["page_no"] for query in queries] == ["1", "2"]
    assert all(query["brand_type"] == code and type(query["brand_type"]) is str for query in queries)
    assert all(query["price_bin"] == ("20-100" if price else "不限") for query in queries)
    with _api_client(context) as client:
        page = client.get("/api/v1/product-selection/candidates", headers=headers).json()
        assert page["total"] == 2
        assert all(row["source_context"]["business"]["brand_type"] == code for row in page["items"])
        assert client.get("/api/v1/product-selection/candidates", headers=headers).json() == page
        assert client.get(f"/api/v1/product-selection/strategies/{saved.strategy_id}", headers=headers).json()["conditions"]["request"]["brand"] == brand
    assert len(queries) == 2


@pytest.mark.parametrize("brand", ["known", "unknown"])
def test_brand_success_empty_fallback_preserves_actual_brand(selection_context, brand):
    receipt = _submit(selection_context, _branded(selection_context, brand, rank_to=10))
    platform = WindowPlatform(receipt.execution.request_conditions, {("primary", 1): (), ("backup", 1): (_product(rank=1),)})
    _executor(selection_context, platform).execute_available()
    run = _get(selection_context, receipt)
    assert run.status == "succeeded" and run.request_conditions.date_outcome.state == "backup"
    assert platform.rank_calls == [("primary", 1), ("backup", 1)]
    assert run.request_conditions.actual_scope().brand_type == ("1" if brand == "known" else "0")


@pytest.mark.parametrize("code", [621000704, "621000704"])
def test_brand_business_rejection_never_uses_default_probe(selection_context, code):
    receipt = _submit(selection_context, _branded(selection_context, rank_to=10))
    platform = WindowPlatform(receipt.execution.request_conditions, {("primary", 1): CompassSelectionBusinessError(details={"platform_code": code})})
    _executor(selection_context, platform).execute_available()
    run = _get(selection_context, receipt)
    assert run.status == "failed" and run.platform_business_code == code and run.result_count is None
    assert run.request_conditions.date_outcome is None and platform.rank_calls == [("primary", 1)]
