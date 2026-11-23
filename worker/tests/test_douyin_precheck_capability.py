import asyncio
from datetime import UTC, datetime, timedelta
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import httpx

from app.contracts import ExecutionStatus, WorkerTask
from app.rpa_session_bridge import RpaBridgeError


path = Path(__file__).resolve().parents[1] / "capabilities" / "douyin_category_schema" / "capability.py"
spec = importlib.util.spec_from_file_location("douyin_capability_for_test", path)
capability = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capability)


class Host:
    device_id = uuid4()
    platform_calls = 0

    def __init__(self, code):
        self.code = code

    async def read_session(self, local_shop_id, platform_shop_id):
        return SimpleNamespace(user_agent="synthetic-agent")

    def cookie_header(self, session):
        return "session=synthetic-cookie"

    async def sign_precheck(self, task_id, cookie, user_agent):
        return {"url": "synthetic", "body": "synthetic"}

    async def post_schema(self, signed, cookie, user_agent, params):
        self.platform_calls += 1
        return 200, {"code": self.code, "data": {"model": {"category_properties": {"items": [
            {"id": "size", "label": "规格", "rules": [{"type": "max_input_num", "value": 3}],
             "ignored": "must-not-persist", "options": [{"id": 1, "name": "小"}]}
        ]}}}}


def task():
    return WorkerTask(task_id=uuid4(), skill_id="douyin.category_schema",
        input={"category_id": "1000005146", "title": "demo", "local_shop_id": "a", "platform_shop_id": "123"},
        lease_until=datetime.now(UTC) + timedelta(seconds=60))


@pytest.mark.parametrize("platform_code", [0, "0"])
def test_success_normalizes_numeric_code_and_keeps_only_safe_fields(platform_code):
    host = Host(platform_code)
    result = asyncio.run(capability.execute(host, task()))
    assert result.status is ExecutionStatus.SUCCESS
    assert result.result["platform_code"] == 0
    assert result.result["items"][0]["rules"] == [{"type": "max_input_num", "value": 3}]
    assert "ignored" not in result.result["items"][0]
    assert "synthetic-cookie" not in repr(result)
    assert host.platform_calls == 1


def test_schema_field_hints_survive_without_product_values_or_unknown_shapes():
    class HintHost(Host):
        async def post_schema(self, signed, cookie, user_agent, params):
            return 200, {"code": 0, "data": {"model": {"category_properties": {"items": [
                {"id": "one", "label": "数量", "placeholder": "请选择数量", "value": "synthetic-secret"},
                {"id": "two", "label": "属性", "placeholder": {"cookie": "synthetic-secret"}},
                {"id": "three", "label": "属性", "placeholder": "x" * 501},
            ]}}}}

    result = asyncio.run(capability.execute(HintHost(0), task()))
    assert result.status is ExecutionStatus.SUCCESS
    items = result.result["items"]
    assert items[0]["placeholder"] == "请选择数量"
    assert "placeholder" not in items[1] and "placeholder" not in items[2]
    assert "synthetic-secret" not in repr(result)


def test_schema_preserves_observed_per_unit_limits_without_inventing_a_missing_unit():
    rules = [{"unit_id": 6, "min": 1, "max": 1825},
             {"unit_id": 7, "min": 0.033, "max": 60.833},
             {"unit_id": 10, "min": 0.003, "max": 5.069}]

    class UnitRuleHost(Host):
        async def post_schema(self, signed, cookie, user_agent, params):
            return 200, {"code": 0, "data": {"model": {"category_properties": {"items": [{
                "id": "2988", "required": False,
                "additions": {"ui_type": "measure", "measure_templates": [{"template_id": 182,
                    "value_modules": [{"module_id": 432, "input_type": "input", "value_required": True,
                        "unit_linkage": None, "extra": {"unit_rule_type": "分单位"},
                        "unit_options": [{"label": "天", "value": 6}, {"label": "月", "value": 7},
                                         {"label": "年", "value": 10}, {"label": "个月", "value": 242}],
                        "validate_rule": {"data_type": "float", "precision": 3,
                                          "min": None, "max": None, "unit_rules": rules}}]}]},
                "value": "synthetic-sensitive-product-value"}]}}}}

    result = asyncio.run(capability.execute(UnitRuleHost(0), task()))
    assert result.status is ExecutionStatus.SUCCESS
    field = result.result["items"][0]
    module = field["additions"]["measure_templates"][0]["value_modules"][0]
    assert field["required"] is False and module["value_required"] is True
    assert module["unit_linkage"] is None and "extra" not in module
    assert module["validate_rule"]["unit_rules"] == rules
    assert {unit["value"] for unit in module["unit_options"]} == {6, 7, 10, 242}
    assert 242 not in {rule["unit_id"] for rule in module["validate_rule"]["unit_rules"]}
    assert "synthetic-sensitive-product-value" not in repr(result)


@pytest.mark.parametrize(("raw", "expected"), [
    (None, None), ([], []), ([{"present": True}], [{"present": True}]),
    ([{"unit_id": 6, "min": None, "max": None}], [{"unit_id": 6, "min": None, "max": None}]),
    ([{"unit_id": 6, "min": 1, "max": 2, "cookie": "synthetic-secret"}], [{"present": True}]),
    ([{"unit_id": 6, "min": 1, "max": 2},
      {"unit_id": 7, "min": 1, "max": 2, "future_rule": True}], [{"present": True}]),
    ([{"unit_id": 6, "min": 1}], [{"present": True}]),
    ([{"unit_id": 6, "min": 1, "max": 2}, {"unit_id": 6, "min": 1, "max": 2}], [{"present": True}]),
    ([{"unit_id": 6, "min": 3, "max": 2}], [{"present": True}]),
    ([{"unit_id": True, "min": 1, "max": 2}], [{"present": True}]),
    ([{"unit_id": 6, "min": False, "max": 2}], [{"present": True}]),
    ([{"unit_id": 6, "min": float("nan"), "max": 2}], [{"present": True}]),
    ([{"unit_id": 6, "min": 1, "max": {"secret": "synthetic-secret"}}], [{"present": True}]),
    ({"unit_id": 6, "min": 1, "max": 2}, [{"present": True}]),
])
def test_unknown_unit_rule_shapes_remain_unknown_without_leaking(raw, expected):
    projected = capability._project({"unit_rules": raw}, "validation")
    assert projected["unit_rules"] == expected
    assert "synthetic-secret" not in repr(projected)


def test_unknown_unit_linkage_remains_a_presence_marker():
    projected = capability._project({"unit_linkage": {"cookie": "synthetic-secret"}}, "module")
    assert projected == {"unit_linkage": {"present": True}}


def test_material_template_options_and_matching_picture_rule_are_sanitized():
    # Metadata shape observed in the platform's 1000010274 page schema. The
    # returned picture values and unrelated fields are deliberately excluded.
    class PictureHost(Host):
        async def post_schema(self, signed, cookie, user_agent, params):
            return 200, {"code": 0, "data": {"model": {
                "category_properties": {"items": [{"id": "785", "label": "面料材质",
                    "additions": {"ui_type": "multi_value_measure", "diy_type": 1,
                        "measure_templates": [{"template_id": 873, "value_modules": [{
                            "module_id": 1854, "input_type": "enum_diy", "value_options": [
                                {"label": "棉", "value": "棉", "private": "synthetic-secret"},
                                {"label": "木棉", "value": "木棉"},
                            ]}]}]}}]},
                "category_property_pic": {"available": True, "items": [{
                    "id": "785", "label": "水洗标/吊牌图", "label_tips": "上传图片可智能识别并预填材质信息",
                    "required": False, "hidden": False, "available": True,
                    "value": {"urls": ["synthetic-secret"]}, "events": {"secret": "synthetic-secret"}}]}}}}

    result = asyncio.run(capability.execute(PictureHost(0), task()))
    assert result.status is ExecutionStatus.SUCCESS
    field = result.result["items"][0]
    options = field["additions"]["measure_templates"][0]["value_modules"][0]["value_options"]
    assert options == [{"label": "棉", "value": "棉"}, {"label": "木棉", "value": "木棉"}]
    assert field["property_picture"] == {"id": "785", "label": "水洗标/吊牌图", "required": False,
                                         "label_tips": "上传图片可智能识别并预填材质信息"}
    assert "synthetic-secret" not in repr(result)


def test_picture_rule_requires_an_unambiguous_visible_platform_field():
    items = [{"id": "785"}, {"id": "other"}]
    field = {"id": "785", "label": "水洗标", "required": False}
    capability._picture_rules({"category_property_pic": {"items": [field]}}, items)
    assert "property_picture" in items[0] and "property_picture" not in items[1]
    for group in (
        {"hidden": True, "items": [field]},
        {"items": [{**field, "hidden": True}]},
        {"items": [{"id": "785", "label": "水洗标"}]},
        {"items": [field, field]},
    ):
        result = [{"id": "785"}]
        capability._picture_rules({"category_property_pic": group}, result)
        assert "property_picture" not in result[0]


@pytest.mark.parametrize(("platform_code", "expected"), [(True, None), ("00", "00"), ("E_600.2-A", "E_600.2-A")])
def test_business_rejection_preserves_safe_code(platform_code, expected):
    result = asyncio.run(capability.execute(Host(platform_code), task()))
    assert result.status is ExecutionStatus.FAILED
    assert result.result["platform_code"] == expected
    assert result.result["error_stage"] == "platform"


@pytest.mark.parametrize(("message", "expected"), [
    ("登录状态已过期，请重新登录", "SHOP_SESSION_EXPIRED"),
    ("请先登录", "SHOP_SESSION_EXPIRED"),
    ("无权访问此接口", "PLATFORM_BUSINESS_REJECTED"),
    ("本次请求存在安全风险", "PLATFORM_BUSINESS_REJECTED"),
    ("网络异常，请稍后重试", "PLATFORM_BUSINESS_REJECTED"),
])
def test_only_explicit_login_failures_invalidate_a_session(message, expected):
    class RejectedHost(Host):
        async def post_schema(self, signed, cookie, user_agent, params):
            return 200, {"code": 10004, "msg": message}

    result = asyncio.run(capability.execute(RejectedHost(10004), task()))
    assert result.status is ExecutionStatus.FAILED
    assert result.error_code == expected


@pytest.mark.parametrize("http_status", [403, 500, 503])
def test_http_or_network_failure_alone_does_not_invalidate_session(http_status):
    class NetworkHost(Host):
        async def post_schema(self, signed, cookie, user_agent, params):
            raise TimeoutError()

    class ForbiddenHost(Host):
        async def post_schema(self, signed, cookie, user_agent, params):
            return http_status, {"code": 10004, "msg": "请先登录"}

    assert asyncio.run(capability.execute(NetworkHost(0), task())).error_code == "PLATFORM_REQUEST_FAILED"
    assert asyncio.run(capability.execute(ForbiddenHost(0), task())).error_code == "PLATFORM_BUSINESS_REJECTED"


def test_unauthorized_with_explicit_login_message_invalidates_session():
    class UnauthorizedHost(Host):
        async def post_schema(self, signed, cookie, user_agent, params):
            return 401, {"code": 10004, "msg": "请先登录"}

    assert asyncio.run(capability.execute(UnauthorizedHost(0), task())).error_code == "SHOP_SESSION_EXPIRED"


def test_queued_known_expired_snapshot_never_calls_platform():
    class NoRequestHost(Host):
        async def read_session(self, local_shop_id, platform_shop_id):
            raise AssertionError("known-expired session must not be read")

    queued = task()
    queued.input["skip_expired_session"] = True
    host = NoRequestHost(0)
    result = asyncio.run(capability.execute(host, queued))
    assert result.error_code == "SHOP_SESSION_EXPIRED"
    assert host.platform_calls == 0


def test_session_bridge_timeout_is_reported_without_signing_or_platform_request():
    class TimedOutHost(Host):
        async def read_session(self, local_shop_id, platform_shop_id):
            raise RpaBridgeError("RPA_BRIDGE_SESSION_TIMEOUT")

        async def sign_precheck(self, *args):
            raise AssertionError("signer must not be called")

    host = TimedOutHost(0)
    result = asyncio.run(capability.execute(host, task()))
    assert result.status is ExecutionStatus.FAILED
    assert result.result["error_stage"] == "session"
    assert result.result["safe_error_code"] == "RPA_BRIDGE_SESSION_TIMEOUT"
    assert host.platform_calls == 0


@pytest.mark.parametrize(("operation", "path", "data"), [
    ("tree", "/product/tproduct/categoryOptionsN", [{"id": 1, "name": "家居", "is_leaf": False,
                                                       "parent_cid": 0, "ignored": "synthetic-secret"}]),
    ("search", "/product/tproduct/searchCategoryN", [{"id": 2, "name": "床品", "ignored": "synthetic-secret"}]),
    ("predict", "/product/tproduct/predictCategoryN", {"predict_cid": 3, "candidate_category_details": [
        {"first_cid": 3, "first_cname": "服饰", "deleted": False, "forbidden_status": 0,
         "ignored": "synthetic-secret"}]}),
])
def test_category_lookup_uses_local_session_and_projects_result(operation, path, data):
    params = {"category_id": "0", "title": "商品", "local_shop_id": "a", "platform_shop_id": "123",
              "operation": operation}
    if operation == "predict":
        params["image_url"] = "https://image.test/a.jpg"
    calls = []

    class LookupHost(Host):
        def __init__(self):
            self._transport = httpx.MockTransport(lambda request: (calls.append(request), httpx.Response(200, json={
                "code": 0, "data": data}))[1])

        async def read_session(self, local_shop_id, platform_shop_id):
            from pydantic import SecretStr
            return SimpleNamespace(user_agent="synthetic-agent", cookies=[
                SimpleNamespace(name="session", value=SecretStr("synthetic-cookie"),
                                domain=".jinritemai.com", path="/")])

        async def sign_precheck(self, task_id, cookie, user_agent):
            query = {"appid": "1", "_bid": "ffa_goods", "_lid": "1", "a_bogus": "synthetic-signature"}
            if operation == "tree":
                query.update({"cid": "0", "display_all": "0"})
            if operation == "search":
                query.update({"key": "商品", "search_type": "1"})
            body = (json.dumps({"title": "商品", "pic": [{"url": params["image_url"]}],
                                "scene": "predict_by_title_and_img"}) if operation == "predict" else "")
            return {"url": str(httpx.URL("https://fxg.jinritemai.com" + path, params=query)), "body": body}

    lookup_task = task()
    lookup_task.input = params
    result = asyncio.run(capability.execute(LookupHost(), lookup_task))
    assert result.status is ExecutionStatus.SUCCESS
    assert result.result["operation"] == operation and len(calls) == 1
    assert "synthetic-secret" not in json.dumps(result.result)
    assert "synthetic-cookie" not in repr(result)


def test_category_lookup_rejects_a_wrong_target_without_request():
    host = Host(0)
    host._transport = httpx.MockTransport(lambda request: pytest.fail("unexpected request"))
    signed = {"url": "https://untrusted.invalid/product/tproduct/predictCategoryN?a_bogus=x", "body": "{}"}
    with pytest.raises(RuntimeError, match="PRECHECK_TRANSPORT_FAILED"):
        asyncio.run(capability._post_lookup(host, signed, "synthetic-cookie", "agent", {"operation": "predict"}))


@pytest.mark.parametrize("display_all", ["0", "1"])
def test_category_tree_accepts_both_signed_scopes_without_losing_platform_status(display_all):
    calls = []
    host = Host(0)
    host._transport = httpx.MockTransport(lambda request: (calls.append(request), httpx.Response(200, json={
        "code": 0, "data": [{"id": "1000011128", "name": "热水袋", "is_leaf": True,
                              "parent_cid": "1000005081", "enable": 1, "industry_status": 2,
                              "secret": "synthetic-secret"}]}))[1])
    signed = {"url": "https://fxg.jinritemai.com/product/tproduct/categoryOptionsN?"
                     f"cid=1000005081&display_all={display_all}&a_bogus=synthetic", "body": ""}
    status, payload = asyncio.run(capability._post_lookup(
        host, signed, "synthetic-cookie", "agent", {"operation": "tree", "category_id": "1000005081"}))
    assert status == 200 and len(calls) == 1
    assert capability._lookup_data("tree", payload["data"]) == [{
        "id": "1000011128", "name": "热水袋", "is_leaf": True, "parent_cid": "1000005081",
        "enable": 1, "industry_status": 2}]


@pytest.mark.parametrize("query", ["display_all=2", "display_all=0&display_all=1", "display_all=1&cid=99"])
def test_category_tree_rejects_invalid_scope_or_duplicate_query(query):
    host = Host(0)
    host._transport = httpx.MockTransport(lambda request: pytest.fail("unexpected request"))
    signed = {"url": "https://fxg.jinritemai.com/product/tproduct/categoryOptionsN?"
                     f"cid=1000005081&{query}&a_bogus=synthetic", "body": ""}
    with pytest.raises(RuntimeError, match="PRECHECK_TRANSPORT_FAILED"):
        asyncio.run(capability._post_lookup(host, signed, "synthetic-cookie", "agent",
                                           {"operation": "tree", "category_id": "1000005081"}))


def test_search_keeps_only_explicit_category_ids_and_never_returns_raw_fields():
    raw = {"list": [{"category_list": [{"id": 10, "name": "餐具"}, {"id": 11, "name": "汤勺"}],
                      "secret": "synthetic-secret"}, {"category_id": 11, "name": "汤勺"}, {"name": "无 ID"}]}
    assert capability._search_candidates(raw) == [{"id": "11", "name": "餐具 > 汤勺", "path": "餐具 > 汤勺"}]
    assert capability._search_candidates({"list": [{"categoryLeafId": 11, "third_cname": "汤勺",
        "first_cname": "餐饮厨具", "second_cname": "餐具"}]}) == [
            {"id": "11", "name": "汤勺", "path": "餐饮厨具 > 餐具 > 汤勺"}]
