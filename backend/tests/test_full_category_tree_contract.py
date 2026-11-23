from types import SimpleNamespace
from uuid import uuid4
from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.modules.workers.precheck_contract import PrecheckInput, supports_full_category_tree, supports_schema_hints, supports_schema_unit_rules, validate_terminal_result
from app.modules.workers.precheck_service import PrecheckUnavailable, _require_current_category_capability, _tree_display_all


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


@pytest.mark.parametrize(("version", "supported"), [
    ("2.0.0", False), ("2.0.1", False), ("2.0.2", True), ("2.1.0", True),
    ("10.0.0", True), ("2.0.2-dev", False), ("", False),
])
def test_schema_hints_require_capability_202_or_newer(version, supported):
    assert supports_schema_hints(version) is supported


def test_schema_hints_are_opt_in_strict_and_schema_only():
    base = {"category_id": "1000010274", "title": "商品"}
    omitted = PrecheckInput.model_validate(base)
    explicit_false = PrecheckInput.model_validate({**base, "require_schema_hints": False})
    required = PrecheckInput.model_validate({**base, "require_schema_hints": True})
    assert omitted.require_schema_hints is False and required.require_schema_hints is True
    assert omitted.model_dump(mode="json", exclude_defaults=True) == explicit_false.model_dump(mode="json", exclude_defaults=True) == base
    assert required.model_dump(mode="json", exclude_defaults=True)["require_schema_hints"] is True
    for value in ("true", 1, None):
        with pytest.raises(ValidationError):
            PrecheckInput.model_validate({**base, "require_schema_hints": value})
    for operation in ("tree", "search", "predict"):
        with pytest.raises(ValidationError):
            PrecheckInput.model_validate({**base, "operation": operation, "require_schema_hints": True})


def test_schema_hint_signing_rechecks_version_without_changing_legacy_gate():
    class Session:
        version = "2.0.1"
        def get(self, model, key, **kwargs):
            return SimpleNamespace(skill_version=self.version) if self.version else None

    session, device = Session(), uuid4()
    _require_current_category_capability(session, device)
    with pytest.raises(PrecheckUnavailable):
        _require_current_category_capability(session, device, require_hints=True)
    session.version = "2.0.2"
    _require_current_category_capability(session, device, require_hints=True)
    session.version = None
    with pytest.raises(PrecheckUnavailable):
        _require_current_category_capability(session, device, require_hints=True)


@pytest.mark.parametrize(("version", "supported"), [
    ("2.0.1", False), ("2.0.2", False), ("2.0.3", True), ("2.1.0", True),
    ("10.0.0", True), ("2.0.3-dev", False), ("", False), (None, False),
])
def test_schema_unit_rules_require_capability_203_or_newer(version, supported):
    assert supports_schema_unit_rules(version) is supported


def test_schema_unit_rules_are_opt_in_strict_and_schema_only():
    base = {"category_id": "1000009182", "title": "商品"}
    omitted = PrecheckInput.model_validate(base)
    explicit_false = PrecheckInput.model_validate({**base, "require_schema_unit_rules": False})
    required = PrecheckInput.model_validate({**base, "require_schema_unit_rules": True})
    assert omitted.require_schema_unit_rules is False and required.require_schema_unit_rules is True
    assert omitted.model_dump(mode="json", exclude_defaults=True) == explicit_false.model_dump(mode="json", exclude_defaults=True) == base
    assert required.model_dump(mode="json", exclude_defaults=True)["require_schema_unit_rules"] is True
    for value in ("true", 1, None):
        with pytest.raises(ValidationError):
            PrecheckInput.model_validate({**base, "require_schema_unit_rules": value})
    for operation in ("tree", "search", "predict"):
        with pytest.raises(ValidationError):
            PrecheckInput.model_validate({**base, "operation": operation, "require_schema_unit_rules": True})


def test_unit_rule_signing_rechecks_version_without_changing_existing_gates():
    class Session:
        version = "2.0.2"
        def get(self, model, key, **kwargs):
            return SimpleNamespace(skill_version=self.version) if self.version else None

    session, device = Session(), uuid4()
    _require_current_category_capability(session, device, require_hints=True)
    with pytest.raises(PrecheckUnavailable):
        _require_current_category_capability(session, device, require_unit_rules=True)
    session.version = "2.0.3"
    _require_current_category_capability(session, device, require_hints=True, require_unit_rules=True)
    session.version = None
    with pytest.raises(PrecheckUnavailable):
        _require_current_category_capability(session, device, require_unit_rules=True)


def test_central_accepts_only_supported_unit_rules_and_the_old_unknown_sentinel():
    device = uuid4()
    expected = {"category_id": "1000009182", "local_shop_id": "local", "platform_shop_id": "123"}
    rules = [{"unit_id": 6, "min": 1, "max": 1825},
             {"unit_id": 7, "min": 0.033, "max": 60.833},
             {"unit_id": 10, "min": 0.003, "max": 5.069}]
    item = {"id": "2988", "required": False, "additions": {"ui_type": "measure", "measure_templates": [{
        "template_id": 182, "value_modules": [{"module_id": 432, "input_type": "input", "value_required": True,
            "unit_linkage": None, "unit_options": [{"label": "天", "value": 6}, {"label": "个月", "value": 242}],
            "validate_rule": {"data_type": "float", "precision": 3, "min": None, "max": None, "unit_rules": rules}}]}]}}
    result = {"kind": "douyin.category_schema", **expected, "device_id": str(device),
              "http_status": 200, "platform_code": 0, "items": [item]}
    validate_terminal_result(result, success=True, expected=expected, device_id=device)
    module = item["additions"]["measure_templates"][0]["value_modules"][0]
    validation = module["validate_rule"]
    module["unit_linkage"] = {"present": True}
    validate_terminal_result(result, success=True, expected=expected, device_id=device)
    module["unit_linkage"] = {"cookie": "synthetic-secret"}
    with pytest.raises(ValueError):
        validate_terminal_result(result, success=True, expected=expected, device_id=device)
    module["unit_linkage"] = None
    for allowed in (None, [], [{"present": True}], [{"unit_id": 6, "min": None, "max": None}]):
        validation["unit_rules"] = allowed
        validate_terminal_result(result, success=True, expected=expected, device_id=device)
    for invalid in ([{"present": 1}], [{"unit_id": 6, "min": 1, "max": 2, "cookie": "synthetic-secret"}],
                    [{"unit_id": 6, "min": 1}], [{"unit_id": 6, "min": 1, "max": 2}] * 2,
                    [{"unit_id": True, "min": 1, "max": 2}], [{"unit_id": 6, "min": False, "max": 2}],
                    [{"unit_id": 6, "min": float("nan"), "max": 2}],
                    [{"unit_id": 6, "min": 3, "max": 2}],
                    [{"unit_id": 6, "min": 1, "max": {"secret": "synthetic-secret"}}],
                    {"unit_id": 6, "min": 1, "max": 2}):
        validation["unit_rules"] = invalid
        with pytest.raises(ValueError):
            validate_terminal_result(result, success=True, expected=expected, device_id=device)


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
              "http_status": 200, "platform_code": 0, "items": [{"id": "785", "label": "面料材质", "placeholder": "请选择",
                  "additions": {"measure_templates": [{"value_modules": [{"value_options": [
                      {"label": "棉", "value": "棉"}]}]}]},
                  "property_picture": {"id": "785", "label": "水洗标/吊牌图", "required": False,
                                       "label_tips": "上传图片可识别材质"}}]}
    validate_terminal_result(result, success=True, expected=expected, device_id=device)
    for mutate in ("picture_value", "wrong_picture_id", "option_secret", "placeholder_object", "placeholder_oversized"):
        invalid = deepcopy(result)
        item = invalid["items"][0]
        if mutate == "picture_value":
            item["property_picture"]["value"] = "synthetic-secret"
        elif mutate == "wrong_picture_id":
            item["property_picture"]["id"] = "other"
        elif mutate == "option_secret":
            item["additions"]["measure_templates"][0]["value_modules"][0]["value_options"][0]["cookie"] = "synthetic-secret"
        elif mutate == "placeholder_object":
            item["placeholder"] = {"cookie": "synthetic-secret"}
        else:
            item["placeholder"] = "x" * 501
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
