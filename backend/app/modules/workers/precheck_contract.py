"""The only externally submitted device precheck and its bounded result."""
from __future__ import annotations

import json
import math
import re
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


PRECHECK_KIND = "douyin.category_schema"
ITEMS_LIMIT = 4 * 1024 * 1024
RESULT_LIMIT = ITEMS_LIMIT + 16 * 1024


class PrecheckContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(gt=0, strict=True)
    attempt: int = Field(gt=0, strict=True)


class PrecheckInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category_id: str = Field(pattern=r"^[0-9]{1,32}$")
    title: str = Field(min_length=1, max_length=500)


class PrecheckSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["douyin.category_schema"]
    context: PrecheckContext
    input: PrecheckInput


class LocalShopSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_shop_id: str = Field(min_length=1, max_length=160, alias="localShopId")
    platform_shop_id: str | None = Field(default=None, max_length=160, alias="platformShopId")
    shop_name: str = Field(min_length=1, max_length=200, alias="shopName")
    platform: str = Field(min_length=1, max_length=64)
    browser_open: bool | None = Field(default=None, alias="browserOpen")


class RpaInventoryReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    available: bool
    installation_id: UUID | None = None
    shops: list[LocalShopSummary] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def check_inventory(self) -> RpaInventoryReport:
        if self.available and self.installation_id is None:
            raise ValueError("available inventory requires installation id")
        if not self.available and (self.installation_id is not None or self.shops):
            raise ValueError("unavailable inventory must not replace prior data")
        ids = [shop.local_shop_id for shop in self.shops]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate local shops")
        return self


class PrecheckTerminal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["success", "failed"]
    result: dict[str, Any] | None = None
    error_code: str | None = Field(default=None, max_length=64)
    error_message: str | None = Field(default=None, max_length=500)


class PrecheckSignInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cookie: SecretStr = Field(repr=False)
    user_agent: str = Field(min_length=1, max_length=2048)

    @model_validator(mode="after")
    def validate_sensitive_headers(self) -> PrecheckSignInput:
        cookie = self.cookie.get_secret_value()
        if not cookie or len(cookie) > 32768 or any(c in cookie + self.user_agent for c in "\r\n\0"):
            raise ValueError("invalid request headers")
        return self


_ITEM = {"id", "label", "name", "required", "options", "hidden", "available", "additions", "rules", "type", "multiple", "allow_create"}
_OPTION = {"value_name", "label", "name", "text", "value_id", "value", "id"}
_ADDITIONS = {"ui_type", "diy_type", "measure_templates"}
_TEMPLATE = {"template_id", "display_name", "value_modules"}
_MODULE = {"module_id", "input_type", "validate_rule", "unit_linkage", "unit_options", "prefix", "suffix", "value_required", "required_tips", "module_shading_words"}
_VALIDATION = {"data_type", "unit_rules", "min", "max", "precision"}
_UNIT = {"label", "value"}
_RULE = {"type", "value"}


def _scalar(value: Any) -> None:
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    raise ValueError("non-scalar schema value")


def _object(value: Any, kind: str) -> None:
    allowed = {"item": _ITEM, "option": _OPTION, "additions": _ADDITIONS,
               "template": _TEMPLATE, "module": _MODULE, "validation": _VALIDATION,
               "unit": _UNIT, "rule": _RULE}[kind]
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError("unexpected schema field")
    nested_objects = {("item", "additions"): "additions", ("module", "validate_rule"): "validation"}
    nested_lists = {("item", "options"): "option", ("item", "rules"): "rule",
                    ("additions", "measure_templates"): "template", ("template", "value_modules"): "module",
                    ("module", "unit_options"): "unit"}
    for key, child in value.items():
        if (kind, key) in nested_objects and isinstance(child, dict):
            _object(child, nested_objects[(kind, key)])
        elif (kind, key) in nested_lists and isinstance(child, list):
            for entry in child:
                if entry is not None:
                    _object(entry, nested_lists[(kind, key)])
        elif (kind, key) == ("module", "unit_linkage") and child in (None, {}, {"present": True}):
            pass
        elif (kind, key) == ("validation", "unit_rules") and child in (None, [], [{"present": True}]):
            pass
        else:
            _scalar(child)


def validate_terminal_result(result: dict[str, Any], *, success: bool, expected: dict[str, str], device_id: UUID) -> None:
    required = {"kind", "category_id", "device_id", "local_shop_id", "platform_shop_id", "http_status", "platform_code"}
    if success:
        required.add("items")
    else:
        required |= {"error_stage", "safe_error_code"}
    if set(result) != required:
        raise ValueError("unexpected result fields")
    if (result["kind"] != PRECHECK_KIND or result["device_id"] != str(device_id)
            or any(result[key] != expected[key] for key in ("category_id", "local_shop_id", "platform_shop_id"))):
        raise ValueError("result identity mismatch")
    code = result["platform_code"]
    if code is not None and (isinstance(code, bool) or not isinstance(code, (int, str))
                             or isinstance(code, str) and not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", code)):
        raise ValueError("invalid platform code")
    status = result["http_status"]
    if status is not None and (isinstance(status, bool) or not isinstance(status, int) or not 100 <= status <= 599):
        raise ValueError("invalid http status")
    if success:
        if status != 200 or code not in (0, "0") or not isinstance(result["items"], list):
            raise ValueError("success lacks platform result")
        for item in result["items"]:
            _object(item, "item")
        encoded_items = json.dumps(result["items"], ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(encoded_items) > ITEMS_LIMIT:
            raise ValueError("precheck items exceed the limit")
    elif (result["error_stage"] not in {"session", "signer", "platform", "result"}
          or not isinstance(result["safe_error_code"], str)
          or not result["safe_error_code"].isascii()
          or not result["safe_error_code"].replace("_", "").isalnum()
          or len(result["safe_error_code"]) > 64):
        raise ValueError("invalid safe error")
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(encoded) > RESULT_LIMIT:
        raise ValueError("result exceeds the precheck limit")
