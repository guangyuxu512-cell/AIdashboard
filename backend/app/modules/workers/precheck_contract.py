"""The only externally submitted device precheck and its bounded result."""
from __future__ import annotations

import json
import math
import re
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID, NAMESPACE_URL, uuid5

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, SecretStr, model_validator


PRECHECK_KIND = "douyin.category_schema"
ITEMS_LIMIT = 4 * 1024 * 1024
RESULT_LIMIT = ITEMS_LIMIT + 16 * 1024
CATEGORY_LOOKUP_CAPABILITY_VERSION = (2, 0, 0)
FULL_CATEGORY_TREE_CAPABILITY_VERSION = (2, 0, 1)
SCHEMA_HINTS_CAPABILITY_VERSION = (2, 0, 2)
SCHEMA_UNIT_RULES_CAPABILITY_VERSION = (2, 0, 3)


def mapped_shop_id(platform_shop_id: str) -> UUID:
    """Stable public identifier for the RPA-reported platform shop, not a binding."""
    return uuid5(NAMESPACE_URL, "ecommerce-worker:douyin:" + platform_shop_id)


def supports_category_lookup(version: str) -> bool:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    return bool(match and tuple(int(value) for value in match.groups()) >= CATEGORY_LOOKUP_CAPABILITY_VERSION)


def supports_full_category_tree(version: str) -> bool:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    return bool(match and tuple(int(value) for value in match.groups()) >= FULL_CATEGORY_TREE_CAPABILITY_VERSION)


def supports_schema_hints(version: str) -> bool:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    return bool(match and tuple(int(value) for value in match.groups()) >= SCHEMA_HINTS_CAPABILITY_VERSION)


def supports_schema_unit_rules(version: str) -> bool:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version) if isinstance(version, str) else None
    return bool(match and tuple(int(value) for value in match.groups()) >= SCHEMA_UNIT_RULES_CAPABILITY_VERSION)


class PrecheckContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(gt=0, strict=True)
    attempt: int = Field(gt=0, strict=True)


class PrecheckInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category_id: str = Field(pattern=r"^[0-9]{1,32}$")
    title: str = Field(min_length=1, max_length=10000)
    operation: Literal["schema", "tree", "search", "predict"] = "schema"
    full_category_tree: bool = Field(default=False, strict=True)
    require_schema_metadata: bool = Field(default=False, strict=True)
    require_schema_hints: bool = Field(default=False, strict=True)
    require_schema_unit_rules: bool = Field(default=False, strict=True)
    image_url: str | None = Field(default=None, max_length=10000)
    shop_id: UUID | None = None

    @model_validator(mode="after")
    def validate_operation(self) -> PrecheckInput:
        if self.full_category_tree and self.operation != "tree":
            raise ValueError("full category tree requires tree operation")
        if self.require_schema_metadata and self.operation != "schema":
            raise ValueError("schema metadata requires schema operation")
        if self.require_schema_hints and self.operation != "schema":
            raise ValueError("schema hints require schema operation")
        if self.require_schema_unit_rules and self.operation != "schema":
            raise ValueError("schema unit rules require schema operation")
        if self.operation in {"search", "predict"} and not self.title.strip():
            raise ValueError("invalid title")
        if self.operation == "schema" and len(self.title) > 500:
            raise ValueError("invalid category schema")
        if self.operation in {"search", "predict"} and self.category_id != "0":
            raise ValueError("unexpected category")
        if self.operation == "search" and len(self.title) > 120:
            raise ValueError("invalid search")
        if self.operation == "predict":
            try:
                parsed = urlsplit(self.image_url or "")
                _ = parsed.port
                if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                        or parsed.username is not None or parsed.password is not None
                        or any(ord(value) < 33 or ord(value) == 127 for value in self.image_url or "")):
                    raise ValueError()
            except ValueError:
                raise ValueError("invalid product image") from None
        elif self.image_url is not None:
            raise ValueError("unexpected product image")
        return self


class PrecheckPlatformRetry(BaseModel):
    """Proof of an already delivered, explicitly rejected platform result."""
    model_config = ConfigDict(extra="forbid")
    previous_task_id: UUID
    # Preserve the exact bytes Worker sent to the product service. Never render
    # this in validation output, logs, or the Task record.
    terminal_json: SecretStr = Field(min_length=1, max_length=8192, repr=False)


class PrecheckSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["douyin.category_schema"]
    context: PrecheckContext
    input: PrecheckInput
    delivery: Literal["central", "product"] = "central"
    retry: PrecheckPlatformRetry | None = None


class PrecheckDeliveryAcknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["success", "failed"]
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    error_code: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]{2,63}$")

    @model_validator(mode="after")
    def check_status(self) -> PrecheckDeliveryAcknowledgement:
        if (self.status == "success" and self.error_code is not None) or (self.status == "failed" and not self.error_code):
            raise ValueError("invalid delivery status")
        return self


class LocalShopSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_shop_id: str = Field(min_length=1, max_length=160, alias="localShopId")
    platform_shop_id: str | None = Field(default=None, max_length=160, alias="platformShopId")
    shop_name: str = Field(min_length=1, max_length=200, alias="shopName")
    platform: str = Field(min_length=1, max_length=64)
    browser_open: bool | None = Field(default=None, alias="browserOpen")
    session_stored: bool = Field(default=False, alias="sessionStored")
    session_revision: str | None = Field(default=None, alias="sessionRevision", pattern=r"^[0-9a-f]{64}$")
    compass_session_verified: bool | None = Field(default=None, alias="compassSessionVerified", strict=True)
    session_status: Literal["valid", "invalid"] | None = Field(default=None, alias="sessionStatus")
    session_checked_at: AwareDatetime | None = Field(default=None, alias="sessionCheckedAt")
    compass_session_status: Literal["valid", "invalid"] | None = Field(default=None, alias="compassSessionStatus")
    compass_session_checked_at: AwareDatetime | None = Field(default=None, alias="compassSessionCheckedAt")

    @model_validator(mode="after")
    def check_session_observation(self) -> LocalShopSummary:
        if (self.session_status is None) != (self.session_checked_at is None):
            raise ValueError("session status and check time must be paired")
        if (self.compass_session_status is None) != (self.compass_session_checked_at is None):
            raise ValueError("compass session status and check time must be paired")
        if (self.session_status is not None or self.compass_session_status is not None) and (
            not self.session_stored or not self.session_revision or not self.platform_shop_id
            or self.platform != "douyin"
        ):
            raise ValueError("session observation requires the saved shop snapshot")
        if self.compass_session_verified is True and (
            not self.session_stored or not self.session_revision or not self.platform_shop_id or self.platform != "douyin"
        ):
            raise ValueError("compass verification requires the saved shop snapshot")
        return self


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


_ITEM = {"id", "label", "name", "placeholder", "required", "options", "hidden", "available", "additions", "rules", "type", "multiple", "allow_create", "property_picture"}
_OPTION = {"value_name", "label", "name", "text", "value_id", "value", "id"}
_ADDITIONS = {"ui_type", "diy_type", "measure_templates"}
_TEMPLATE = {"template_id", "display_name", "value_modules"}
_MODULE = {"module_id", "input_type", "validate_rule", "unit_linkage", "unit_options", "value_options", "prefix", "suffix", "value_required", "required_tips", "module_shading_words"}
_VALIDATION = {"data_type", "unit_rules", "min", "max", "precision"}
_UNIT = {"label", "value"}
_RULE = {"type", "value"}
_PICTURE = {"id", "label", "required", "label_tips"}


def _scalar(value: Any) -> None:
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    raise ValueError("non-scalar schema value")


def _unit_rules(value: Any) -> None:
    """Validate known unit-specific bounds or the existing unknown sentinel."""
    if value is None:
        return
    if not isinstance(value, list):
        raise ValueError("invalid unit rules")
    if not value:
        return
    if len(value) == 1 and isinstance(value[0], dict) and set(value[0]) == {"present"} and value[0]["present"] is True:
        return
    seen: set[int] = set()
    for entry in value:
        if (not isinstance(entry, dict) or set(entry) != {"unit_id", "min", "max"}
                or type(entry["unit_id"]) is not int or entry["unit_id"] <= 0
                or entry["unit_id"] in seen):
            raise ValueError("invalid unit rule")
        minimum, maximum = entry["min"], entry["max"]
        for bound in (minimum, maximum):
            if bound is not None and (type(bound) not in (int, float)
                    or (type(bound) is float and not math.isfinite(bound))):
                raise ValueError("invalid unit rule bound")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError("invalid unit rule range")
        seen.add(entry["unit_id"])


def _object(value: Any, kind: str) -> None:
    allowed = {"item": _ITEM, "option": _OPTION, "additions": _ADDITIONS,
               "template": _TEMPLATE, "module": _MODULE, "validation": _VALIDATION,
               "unit": _UNIT, "rule": _RULE, "picture": _PICTURE}[kind]
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError("unexpected schema field")
    nested_objects = {("item", "additions"): "additions", ("module", "validate_rule"): "validation"}
    nested_lists = {("item", "options"): "option", ("item", "rules"): "rule",
                    ("additions", "measure_templates"): "template", ("template", "value_modules"): "module",
                    ("module", "unit_options"): "unit", ("module", "value_options"): "option"}
    for key, child in value.items():
        if (kind, key) == ("item", "placeholder"):
            if not isinstance(child, str) or len(child) > 500:
                raise ValueError("invalid field placeholder")
        elif (kind, key) == ("item", "property_picture"):
            if (not isinstance(child, dict) or set(child) != _PICTURE
                    or not isinstance(child["id"], str) or child["id"] != str(value.get("id", ""))
                    or not isinstance(child["label"], str) or not child["label"].strip()
                    or type(child["required"]) is not bool or not isinstance(child["label_tips"], str)):
                raise ValueError("invalid property picture rule")
            _object(child, "picture")
        elif (kind, key) in nested_objects and isinstance(child, dict):
            _object(child, nested_objects[(kind, key)])
        elif (kind, key) in nested_lists and isinstance(child, list):
            for entry in child:
                if entry is not None:
                    _object(entry, nested_lists[(kind, key)])
        elif (kind, key) == ("module", "unit_linkage") and child in (None, {}, {"present": True}):
            pass
        elif (kind, key) == ("validation", "unit_rules"):
            _unit_rules(child)
        else:
            _scalar(child)


def validate_category_lookup_data(operation: str, data: Any) -> None:
    """Accept only the non-sensitive category fields consumed by the product app."""
    if operation == "tree":
        if not isinstance(data, list) or len(data) > 10000:
            raise ValueError("invalid category tree")
        for item in data:
            if not isinstance(item, dict) or set(item) - {"id", "name", "is_leaf", "parent_cid", "enable", "industry_status"}:
                raise ValueError("invalid category tree")
            for value in item.values():
                _scalar(value)
        return
    if operation == "predict":
        if not isinstance(data, dict) or set(data) != {"candidate_category_details", "predict_cid"}:
            raise ValueError("invalid category prediction")
        entries = data["candidate_category_details"]
        if not isinstance(entries, list) or len(entries) > 200:
            raise ValueError("invalid category prediction")
        _scalar(data["predict_cid"])
        allowed = {part + suffix for part in ("first", "second", "third", "fourth")
                   for suffix in ("_cid", "_cname")} | {"deleted", "forbidden_status"}
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) - allowed:
                raise ValueError("invalid category prediction")
            for value in entry.values():
                _scalar(value)
        return
    if operation == "search":
        if not isinstance(data, list) or len(data) > 200:
            raise ValueError("invalid category search")
        for item in data:
            if (not isinstance(item, dict) or set(item) != {"id", "name", "path"}
                    or any(not isinstance(item[key], str) for key in ("id", "name", "path"))
                    or not re.fullmatch(r"[0-9]{1,32}", item["id"])
                    or len(item["name"]) > 200 or len(item["path"]) > 500):
                raise ValueError("invalid category search")
        return
    raise ValueError("unknown category lookup")


def validate_terminal_result(result: dict[str, Any], *, success: bool, expected: dict[str, str], device_id: UUID) -> None:
    required = {"kind", "category_id", "device_id", "local_shop_id", "platform_shop_id", "http_status", "platform_code"}
    operation = expected.get("operation", "schema")
    if operation != "schema":
        required.add("operation")
    if success:
        required.add("items" if operation == "schema" else "data")
    else:
        required |= {"error_stage", "safe_error_code"}
    if set(result) != required:
        raise ValueError("unexpected result fields")
    if (result["kind"] != PRECHECK_KIND or result["device_id"] != str(device_id)
            or any(result[key] != expected[key] for key in ("category_id", "local_shop_id", "platform_shop_id"))):
        raise ValueError("result identity mismatch")
    if operation != "schema" and result["operation"] != operation:
        raise ValueError("operation mismatch")
    code = result["platform_code"]
    if code is not None and (isinstance(code, bool) or not isinstance(code, (int, str))
                             or isinstance(code, str) and not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", code)):
        raise ValueError("invalid platform code")
    status = result["http_status"]
    if status is not None and (isinstance(status, bool) or not isinstance(status, int) or not 100 <= status <= 599):
        raise ValueError("invalid http status")
    if success:
        if status != 200 or code not in (0, "0"):
            raise ValueError("success lacks platform result")
        if operation == "schema":
            if not isinstance(result["items"], list):
                raise ValueError("success lacks platform result")
            for item in result["items"]:
                _object(item, "item")
            payload = result["items"]
        else:
            validate_category_lookup_data(operation, result["data"])
            payload = result["data"]
        encoded_items = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
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
