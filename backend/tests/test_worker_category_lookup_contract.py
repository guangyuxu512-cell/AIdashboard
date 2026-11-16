from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.workers.precheck_contract import (
    PrecheckInput, mapped_shop_id, supports_category_lookup, validate_terminal_result,
)


def test_existing_schema_hash_input_is_unchanged():
    data = PrecheckInput(category_id="123", title="商品")
    assert data.model_dump(mode="json", exclude_defaults=True) == {"category_id": "123", "title": "商品"}
    assert not supports_category_lookup("1.9.9")
    assert supports_category_lookup("2.0.0")
    assert mapped_shop_id("shop-1") == mapped_shop_id("shop-1") != mapped_shop_id("shop-2")


def test_prediction_accepts_only_frozen_image_and_explicit_operation():
    data = PrecheckInput(category_id="0", title="商品", operation="predict", image_url="https://image.test/a.jpg")
    assert data.operation == "predict"
    with pytest.raises(ValidationError):
        PrecheckInput(category_id="0", title="商品", operation="predict", image_url="file:///secret")
    with pytest.raises(ValidationError):
        PrecheckInput(category_id="123", title="商品", operation="predict", image_url="https://image.test/a.jpg")


def test_only_safe_category_fields_and_assigned_identity_are_accepted():
    device = uuid4()
    expected = {"operation": "predict", "category_id": "0", "local_shop_id": "local", "platform_shop_id": "shop"}
    result = {"kind": "douyin.category_schema", "operation": "predict", "category_id": "0",
              "device_id": str(device), "local_shop_id": "local", "platform_shop_id": "shop",
              "http_status": 200, "platform_code": 0,
              "data": {"predict_cid": "1", "candidate_category_details": [{"first_cid": "1", "first_cname": "服饰"}]}}
    validate_terminal_result(result, success=True, expected=expected, device_id=device)
    result["data"]["cookie"] = "synthetic-secret"
    with pytest.raises(ValueError):
        validate_terminal_result(result, success=True, expected=expected, device_id=device)
