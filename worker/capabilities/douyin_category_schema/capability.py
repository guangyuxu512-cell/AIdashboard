"""Signed Worker capability: read-only Douyin category schema precheck."""
from __future__ import annotations

import json
import re

from app.contracts import ExecutionResult, ExecutionStatus


SKILL_ID = "douyin.category_schema"
MAX_ITEMS = 4 * 1024 * 1024
MAX_RESULT = MAX_ITEMS + 16 * 1024
INPUT_SCHEMA = {"type": "object", "properties": {
    "category_id": {"type": "string"}, "title": {"type": "string"},
    "local_shop_id": {"type": "string"}, "platform_shop_id": {"type": "string"}},
    "required": ["category_id", "title", "local_shop_id", "platform_shop_id"],
    "additionalProperties": False}
_ITEM = {"id", "label", "name", "required", "options", "hidden", "available", "additions", "rules", "type", "multiple", "allow_create"}
_OPTION = {"value_name", "label", "name", "text", "value_id", "value", "id"}
_ADDITIONS = {"ui_type", "diy_type", "measure_templates"}
_TEMPLATE = {"template_id", "display_name", "value_modules"}
_MODULE = {"module_id", "input_type", "validate_rule", "unit_linkage", "unit_options", "prefix", "suffix", "value_required", "required_tips", "module_shading_words"}
_VALIDATION = {"data_type", "unit_rules", "min", "max", "precision"}
_UNIT = {"label", "value"}
_RULE = {"type", "value"}


def _safe_scalar(value):
    if value is None or type(value) in (str, int, float, bool):
        return value
    # This is not a field understood by the existing product normalizer.
    return None


def _project(value, kind):
    if not isinstance(value, dict):
        return None
    allowed = {"item": _ITEM, "option": _OPTION, "additions": _ADDITIONS,
               "template": _TEMPLATE, "module": _MODULE, "validation": _VALIDATION,
               "unit": _UNIT, "rule": _RULE}[kind]
    nested_objects = {("item", "additions"): "additions", ("module", "validate_rule"): "validation"}
    nested_lists = {("item", "options"): "option", ("item", "rules"): "rule",
                    ("additions", "measure_templates"): "template", ("template", "value_modules"): "module",
                    ("module", "unit_options"): "unit"}
    output = {}
    for key in allowed & value.keys():
        child = value[key]
        if (kind, key) in nested_objects and isinstance(child, dict):
            output[key] = _project(child, nested_objects[(kind, key)])
        elif (kind, key) in nested_lists and isinstance(child, list):
            # PDC treats invalid measure/template/unit entries as unknown; do
            # not remove them and accidentally make the remaining rule valid.
            output[key] = [_project(part, nested_lists[(kind, key)]) for part in child]
        elif (kind, key) == ("module", "unit_linkage"):
            output[key] = None if child is None else ({} if child == {} else {"present": True})
        elif (kind, key) == ("validation", "unit_rules"):
            output[key] = None if child is None else ([] if child == [] else [{"present": True}])
        else:
            output[key] = _safe_scalar(child)
    return output


def _platform_code(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"(?:0|[1-9][0-9]*)", value):
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", value):
        return value
    return None


def _failure(identity, stage, code, http_status=None, platform_code=None):
    return ExecutionResult(status=ExecutionStatus.FAILED,
        result={**identity, "http_status": http_status, "platform_code": platform_code,
                "error_stage": stage, "safe_error_code": code},
        error_code=code, error_message="设备预检未完成")


async def execute(host, task):
    params = task.input
    identity = {"kind": SKILL_ID, "category_id": params["category_id"],
                "device_id": str(host.device_id), "local_shop_id": params["local_shop_id"],
                "platform_shop_id": params["platform_shop_id"]}
    try:
        session = await host.read_session(params["local_shop_id"], params["platform_shop_id"])
        cookie = host.cookie_header(session)
    except Exception as error:
        code = getattr(error, "code", "RPA_SESSION_UNAVAILABLE")
        if not isinstance(code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", code):
            code = "RPA_SESSION_UNAVAILABLE"
        return _failure(identity, "session", code)
    try:
        signed = await host.sign_precheck(task.task_id, cookie, session.user_agent)
    except Exception:
        return _failure(identity, "signer", "SIGNER_UNAVAILABLE")
    try:
        status, payload = await host.post_schema(signed, cookie, session.user_agent, params)
    except Exception:
        return _failure(identity, "platform", "PLATFORM_REQUEST_FAILED")
    if not isinstance(payload, dict):
        return _failure(identity, "result", "PLATFORM_RESPONSE_INVALID", status)
    raw_code = payload.get("code", payload.get("st", payload.get("errno")))
    code = _platform_code(raw_code)
    if status != 200 or code != 0:
        return _failure(identity, "platform", "PLATFORM_BUSINESS_REJECTED", status, code)
    data = payload.get("data")
    model = data.get("model") if isinstance(data, dict) else None
    group = model.get("category_properties") if isinstance(model, dict) else None
    items = group.get("items") if isinstance(group, dict) else None
    if not isinstance(items, list):
        return _failure(identity, "result", "PLATFORM_SCHEMA_MISSING", status, code)
    result = {**identity, "http_status": status, "platform_code": code,
              "items": [entry for item in items if (entry := _project(item, "item")) is not None]}
    try:
        items_size = len(json.dumps(result["items"], ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8"))
        result_size = len(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8"))
        if items_size > MAX_ITEMS or result_size > MAX_RESULT:
            return _failure(identity, "result", "PRECHECK_RESULT_TOO_LARGE", status, code)
    except (ValueError, TypeError):
        return _failure(identity, "result", "PLATFORM_SCHEMA_INVALID", status, code)
    return ExecutionResult(status=ExecutionStatus.SUCCESS, result=result)
