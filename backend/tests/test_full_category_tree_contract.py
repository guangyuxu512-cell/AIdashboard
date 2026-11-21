from types import SimpleNamespace
from uuid import uuid4
from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.modules.workers.precheck_contract import PrecheckInput, supports_full_category_tree, validate_terminal_result
from app.modules.workers.precheck_service import PrecheckUnavailable, _tree_display_all


@pytest.mark.parametrize(("version", "supported"), [
    ("2.0.0", False), ("2.0.1", True), ("2.1.0", True), ("10.0.0", True),
    ("2.0.1-dev", False), ("", False),
])
def test_full_tree_requires_a_compatible_capability(version, supported):
    assert supports_full_category_tree(version) is supported


def test_full_tree_is_explicit_and_tree_only():
    base = {"category_id": "1000005081", "title": "商品"}
    assert PrecheckInput.model_validate({**base, "operation": "tree"}).full_category_tree is False
    assert PrecheckInput.model_validate({**base, "operation": "tree", "full_category_tree": True}).full_category_tree is True
    with pytest.raises(ValidationError):
        PrecheckInput.model_validate({**base, "operation": "schema", "full_category_tree": True})
    with pytest.raises(ValidationError):
        PrecheckInput.model_validate({**base, "operation": "tree", "full_category_tree": "true"})


def test_schema_metadata_is_explicit_and_schema_only():
    base = {"category_id": "1000010274", "title": "商品"}
    assert PrecheckInput.model_validate(base).require_schema_metadata is False
    assert PrecheckInput.model_validate({**base, "require_schema_metadata": True}).require_schema_metadata is True
    with pytest.raises(ValidationError):
        PrecheckInput.model_validate({**base, "operation": "tree", "require_schema_metadata": True})
    with pytest.raises(ValidationError):
        PrecheckInput.model_validate({**base, "require_schema_metadata": "true"})


@pytest.mark.parametrize(("version", "expected"), [("2.0.0", None), ("2.0.1", "1"), (None, None)])
def test_signing_cannot_downgrade_a_full_tree_request(version, expected):
    class Session:
        def get(self, model, key):
            return SimpleNamespace(skill_version=version) if version else None

    session = Session()
    device = uuid4()
    assert _tree_display_all(session, device, SimpleNamespace(input_json={})) == "0"
    full = SimpleNamespace(input_json={"_full_category_tree": True})
    if expected is None:
        with pytest.raises(PrecheckUnavailable):
            _tree_display_all(session, device, full)
    else:
        assert _tree_display_all(session, device, full) == expected


def test_central_result_accepts_only_safe_material_and_picture_rules():
    device = uuid4()
    expected = {"category_id": "1000010274", "local_shop_id": "local", "platform_shop_id": "123"}
    result = {"kind": "douyin.category_schema", **expected, "device_id": str(device),
              "http_status": 200, "platform_code": 0, "items": [{"id": "785", "label": "面料材质",
                  "additions": {"measure_templates": [{"value_modules": [{"value_options": [
                      {"label": "棉", "value": "棉"}]}]}]},
                  "property_picture": {"id": "785", "label": "水洗标/吊牌图", "required": False,
                                       "label_tips": "上传图片可识别材质"}}]}
    validate_terminal_result(result, success=True, expected=expected, device_id=device)
    for mutate in ("picture_value", "wrong_picture_id", "option_secret"):
        invalid = deepcopy(result)
        item = invalid["items"][0]
        if mutate == "picture_value":
            item["property_picture"]["value"] = "synthetic-secret"
        elif mutate == "wrong_picture_id":
            item["property_picture"]["id"] = "other"
        else:
            item["additions"]["measure_templates"][0]["value_modules"][0]["value_options"][0]["cookie"] = "synthetic-secret"
        with pytest.raises(ValueError):
            validate_terminal_result(invalid, success=True, expected=expected, device_id=device)


def test_central_tree_result_preserves_platform_status_but_rejects_extra_fields():
    device = uuid4()
    expected = {"category_id": "1000005081", "local_shop_id": "local", "platform_shop_id": "123", "operation": "tree"}
    result = {"kind": "douyin.category_schema", **expected, "device_id": str(device), "http_status": 200,
              "platform_code": 0, "data": [{"id": "1000011128", "name": "热水袋", "is_leaf": True,
                                              "parent_cid": "1000005081", "enable": 1, "industry_status": 2}]}
    validate_terminal_result(result, success=True, expected=expected, device_id=device)
    result["data"][0]["cookie"] = "synthetic-secret"
    with pytest.raises(ValueError):
        validate_terminal_result(result, success=True, expected=expected, device_id=device)
