"""Signed Worker capability: read-only Douyin category schema precheck."""
from __future__ import annotations

import json
import re
from urllib.parse import parse_qsl, urlsplit

import httpx

from app.contracts import ExecutionResult, ExecutionStatus


SKILL_ID = "douyin.category_schema"
MAX_ITEMS = 4 * 1024 * 1024
MAX_RESULT = MAX_ITEMS + 16 * 1024
INPUT_SCHEMA = {"type": "object", "properties": {
    "category_id": {"type": "string"}, "title": {"type": "string"},
    "local_shop_id": {"type": "string"}, "platform_shop_id": {"type": "string"},
    "operation": {"type": "string", "enum": ["schema", "tree", "search", "predict"]},
    "image_url": {"type": "string"},
    "skip_expired_session": {"type": "boolean"}},
    "required": ["category_id", "title", "local_shop_id", "platform_shop_id"],
    "additionalProperties": False}
_ITEM = {"id", "label", "name", "required", "options", "hidden", "available", "additions", "rules", "type", "multiple", "allow_create"}
_OPTION = {"value_name", "label", "name", "text", "value_id", "value", "id"}
_ADDITIONS = {"ui_type", "diy_type", "measure_templates"}
_TEMPLATE = {"template_id", "display_name", "value_modules"}
_MODULE = {"module_id", "input_type", "validate_rule", "unit_linkage", "unit_options", "value_options", "prefix", "suffix", "value_required", "required_tips", "module_shading_words"}
_VALIDATION = {"data_type", "unit_rules", "min", "max", "precision"}
_UNIT = {"label", "value"}
_RULE = {"type", "value"}
_EXPLICIT_LOGIN_FAILURES = {
    "未登录", "用户未登录", "请先登录", "请重新登录", "登录失效", "登录已失效",
    "登录过期", "登录已过期", "登录状态失效", "登录状态已失效", "登录状态已过期",
    "登录失效请重新登录", "登录过期请重新登录", "登录状态已失效请重新登录",
    "登录状态已过期请重新登录", "sessionexpired", "loginrequired", "notloggedin",
}


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
                    ("module", "unit_options"): "unit", ("module", "value_options"): "option"}
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


def _picture_rules(model, items):
    """Attach visible platform image-field definitions, never image values."""
    group = model.get("category_property_pic")
    if (not isinstance(group, dict) or group.get("hidden") is True
            or group.get("available") is False or not isinstance(group.get("items"), list)):
        return
    by_id = {}
    duplicates = set()
    for picture in group["items"]:
        if not isinstance(picture, dict):
            continue
        identity = picture.get("id")
        if isinstance(identity, bool) or not isinstance(identity, (str, int)) or not str(identity).strip():
            continue
        identity = str(identity)
        if identity in by_id:
            duplicates.add(identity)
            continue
        label, required = picture.get("label"), picture.get("required")
        if (picture.get("hidden") is True or picture.get("available") is False
                or not isinstance(label, str) or not label.strip() or type(required) is not bool):
            continue
        tip = picture.get("label_tips")
        by_id[identity] = {"id": identity, "label": label, "required": required,
                           "label_tips": tip if isinstance(tip, str) else ""}
    for item in items:
        identity = str(item.get("id", ""))
        if identity in by_id and identity not in duplicates:
            item["property_picture"] = by_id[identity]


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


def _explicit_login_failure(payload):
    """Only an explicit login message qualifies; denial or risk alone do not."""
    if not isinstance(payload, dict):
        return False
    for key in ("message", "msg", "error_msg", "error_message"):
        value = payload.get(key)
        if not isinstance(value, str) or len(value) > 120:
            continue
        normalized = re.sub(r"[\s，。！？、:：!,.；;]+", "", value).lower()
        if normalized in _EXPLICIT_LOGIN_FAILURES:
            return True
    return False


def _failure(identity, stage, code, http_status=None, platform_code=None):
    return ExecutionResult(status=ExecutionStatus.FAILED,
        result={**identity, "http_status": http_status, "platform_code": platform_code,
                "error_stage": stage, "safe_error_code": code},
        error_code=code, error_message="设备预检未完成")


def _lookup_cookie(session, operation):
    """Let the HTTP cookie jar select the local Session for the actual path."""
    paths = {"tree": "/product/tproduct/categoryOptionsN", "search": "/product/tproduct/searchCategoryN",
             "predict": "/product/tproduct/predictCategoryN"}
    cookies = httpx.Cookies()
    for cookie in session.cookies:
        cookies.set(cookie.name, cookie.value.get_secret_value(), domain=cookie.domain, path=cookie.path)
    request = httpx.Request("POST", "https://fxg.jinritemai.com" + paths[operation], cookies=cookies)
    value = request.headers.get("cookie", "")
    if not value:
        raise ValueError("session unavailable")
    return value


async def _post_lookup(host, signed, cookie, user_agent, params):
    """Run only the frozen category operation; never accept a task-supplied URL."""
    operation = params["operation"]
    paths = {"tree": ("GET", "/product/tproduct/categoryOptionsN"),
             "search": ("GET", "/product/tproduct/searchCategoryN"),
             "predict": ("POST", "/product/tproduct/predictCategoryN")}
    try:
        method, path = paths[operation]
        parsed = urlsplit(signed["url"])
        query = parse_qsl(parsed.query, keep_blank_values=True)
        values = dict(query)
        allowed = {"appid", "_bid", "_lid", "verifyFp", "fp", "msToken", "a_bogus"}
        allowed |= {"cid", "display_all"} if operation == "tree" else {"key", "search_type"} if operation == "search" else set()
        if (parsed.scheme != "https" or parsed.hostname != "fxg.jinritemai.com" or parsed.port is not None
                or parsed.username is not None or parsed.password is not None or parsed.fragment
                or parsed.path != path or len(values) != len(query)
                or set(values) - allowed or not values.get("a_bogus")):
            raise ValueError("invalid signed target")
        if operation == "tree" and (values.get("cid") != params["category_id"] or values.get("display_all") != "0"):
            raise ValueError("category mismatch")
        if operation == "search" and (values.get("key") != params["title"] or values.get("search_type") != "1"):
            raise ValueError("search mismatch")
        body = signed.get("body", "").encode("utf-8")
        if len(body) > 64 * 1024 or (method == "GET" and body):
            raise ValueError("invalid body")
        if operation == "predict":
            data = json.loads(body)
            if (data.get("title") != params["title"] or data.get("pic") != [{"url": params["image_url"]}]
                    or data.get("scene") != "predict_by_title_and_img"):
                raise ValueError("prediction mismatch")
        headers = {"accept": "application/json, text/plain, */*", "user-agent": user_agent,
                   "accept-language": "zh-CN,zh;q=0.9", "cache-control": "no-cache", "pragma": "no-cache",
                   "referer": "https://fxg.jinritemai.com/ffa/g/create", "origin": "https://fxg.jinritemai.com",
                   "cookie": cookie, "x-tt-from-end": "PC", "x-tt-from-appid": "ffa-goods",
                   "x-tt-from-page": "https://fxg.jinritemai.com/ffa/g/create", "x-tt-from-version": "1.0.1.3675",
                   "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"Windows"',
                   "sec-fetch-dest": "empty", "sec-fetch-mode": "cors", "sec-fetch-site": "same-origin"}
        chrome = re.search(r"Chrome/(\d+)", user_agent)
        if chrome:
            major = chrome.group(1)
            headers["sec-ch-ua"] = f'"Chromium";v="{major}", "Google Chrome";v="{major}", "Not/A)Brand";v="99"'
        if method == "POST":
            headers["content-type"] = "application/json;charset=UTF-8"
        for part in cookie.split(";"):
            key, separator, value = part.strip().partition("=")
            if key == "csrf_session_id" and separator:
                headers["x-secsdk-csrf-token"] = value
        async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False,
                                     transport=getattr(host, "_transport", None)) as client:
            async with client.stream(method, signed["url"], headers=headers, content=body or None) as response:
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > 3 * 1024 * 1024:
                        raise ValueError("platform response too large")
                return response.status_code, json.loads(content)
    except (KeyError, TypeError, ValueError, httpx.HTTPError, OSError):
        raise RuntimeError("PRECHECK_TRANSPORT_FAILED") from None


def _search_candidates(value):
    """Keep the existing product-app category search semantics without raw responses."""
    result, seen = [], set()
    path_keys = ("category_list", "categoryList", "category_path_list", "categoryPathList", "path_list", "pathList", "paths", "breadcrumb")
    id_keys = ("category_leaf_id", "categoryLeafId", "leaf_cid", "leafCid", "leaf_category_id", "leafCategoryId",
               "fourth_cid", "fourthCid", "third_cid", "thirdCid", "category_id", "categoryId", "cid", "id", "value")
    name_keys = ("category_name", "categoryName", "name", "label", "title", "third_cname", "thirdCname", "leaf_cname", "leafCname")
    path_names = ("category_path", "categoryPath", "category_path_name", "categoryPathName", "full_path", "fullPath", "path", "full_name", "fullName", "category_full_name", "categoryFullName", "category_name_path", "categoryNamePath")
    level_names = (("first_cname", "firstCname", "first_name", "firstName"),
                   ("second_cname", "secondCname", "second_name", "secondName"),
                   ("third_cname", "thirdCname", "third_name", "thirdName"),
                   ("fourth_cname", "fourthCname", "fourth_name", "fourthName"),
                   ("leaf_cname", "leafCname", "leaf_name", "leafName"))

    def walk(node, depth=0):
        if depth > 12 or len(result) >= 200:
            return
        if isinstance(node, list):
            for child in node[:1000]:
                walk(child, depth + 1)
            return
        if not isinstance(node, dict):
            return
        path_items = next((node[key] for key in path_keys if isinstance(node.get(key), list)), [])
        cid = next((node[key] for key in id_keys if str(node.get(key) or "").isdigit()), None)
        if cid is None:
            for item in reversed(path_items):
                if isinstance(item, dict):
                    cid = next((item[key] for key in id_keys if str(item.get(key) or "").isdigit()), None)
                    if cid is not None:
                        break
        name = next((node[key].strip() for key in name_keys if isinstance(node.get(key), str) and node[key].strip()), "")
        path = next((node[key].strip() for key in path_names if isinstance(node.get(key), str) and node[key].strip()), "")
        if not path and path_items:
            path = " > ".join(str(next((item[key] for key in name_keys if item.get(key)), ""))
                              if isinstance(item, dict) else str(item) for item in path_items)
        if not path:
            levels = [next((node[key].strip() for key in keys if isinstance(node.get(key), str) and node[key].strip()), "")
                      for keys in level_names]
            path = " > ".join(value for index, value in enumerate(levels) if value and (index == 0 or value != levels[index - 1]))
        if cid is not None and (name or path) and str(cid) not in seen:
            seen.add(str(cid))
            result.append({"id": str(cid), "name": (name or path)[-200:], "path": (path or name)[:500]})
        for key, child in node.items():
            if key not in path_keys and isinstance(child, (dict, list)):
                walk(child, depth + 1)
    walk(value)
    return result


def _lookup_data(operation, data):
    if operation == "tree":
        if not isinstance(data, list) or len(data) > 10000:
            raise ValueError("invalid category tree")
        keys = {"id", "name", "is_leaf", "parent_cid", "enable"}
        if not all(isinstance(item, dict) for item in data):
            raise ValueError("invalid category tree")
        return [{key: _safe_scalar(item[key]) for key in keys & item.keys()} for item in data]
    if operation == "predict":
        if not isinstance(data, dict):
            raise ValueError("invalid category prediction")
        entries = data.get("candidate_category_details")
        if entries is None:
            entries = []
        if not isinstance(entries, list) or len(entries) > 200 or not all(isinstance(item, dict) for item in entries):
            raise ValueError("invalid category prediction")
        keys = {part + suffix for part in ("first", "second", "third", "fourth")
                for suffix in ("_cid", "_cname")} | {"deleted", "forbidden_status"}
        return {"candidate_category_details": [{key: _safe_scalar(item[key]) for key in keys & item.keys()}
                                               for item in entries],
                "predict_cid": _safe_scalar(data.get("predict_cid"))}
    if operation == "search":
        return _search_candidates(data)
    raise ValueError("unknown category operation")


async def execute(host, task):
    params = task.input
    operation = params.get("operation", "schema")
    identity = {"kind": SKILL_ID, "category_id": params["category_id"],
                "device_id": str(host.device_id), "local_shop_id": params["local_shop_id"],
                "platform_shop_id": params["platform_shop_id"]}
    if operation != "schema":
        identity["operation"] = operation
    if params.get("skip_expired_session") is True:
        return _failure(identity, "session", "SHOP_SESSION_EXPIRED")
    try:
        session = await host.read_session(params["local_shop_id"], params["platform_shop_id"])
        cookie = host.cookie_header(session) if operation == "schema" else _lookup_cookie(session, operation)
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
        status, payload = (await host.post_schema(signed, cookie, session.user_agent, params)
                           if operation == "schema" else await _post_lookup(host, signed, cookie, session.user_agent, params))
    except Exception:
        return _failure(identity, "platform", "PLATFORM_REQUEST_FAILED")
    if not isinstance(payload, dict):
        return _failure(identity, "result", "PLATFORM_RESPONSE_INVALID", status)
    raw_code = payload.get("code", payload.get("st", payload.get("errno")))
    code = _platform_code(raw_code)
    if status != 200 or code != 0:
        if status in (200, 401) and _explicit_login_failure(payload):
            return _failure(identity, "session", "SHOP_SESSION_EXPIRED", status, code)
        return _failure(identity, "platform", "PLATFORM_BUSINESS_REJECTED", status, code)
    data = payload.get("data")
    if operation != "schema":
        try:
            result = {**identity, "http_status": status, "platform_code": code,
                      "data": _lookup_data(operation, data)}
            if len(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")) > MAX_RESULT:
                raise ValueError("result too large")
        except (ValueError, TypeError):
            return _failure(identity, "result", "PLATFORM_CATEGORY_INVALID", status, code)
        return ExecutionResult(status=ExecutionStatus.SUCCESS, result=result)
    model = data.get("model") if isinstance(data, dict) else None
    group = model.get("category_properties") if isinstance(model, dict) else None
    items = group.get("items") if isinstance(group, dict) else None
    if not isinstance(items, list):
        return _failure(identity, "result", "PLATFORM_SCHEMA_MISSING", status, code)
    projected_items = [entry for item in items if (entry := _project(item, "item")) is not None]
    _picture_rules(model, projected_items)
    result = {**identity, "http_status": status, "platform_code": code, "items": projected_items}
    try:
        items_size = len(json.dumps(result["items"], ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8"))
        result_size = len(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8"))
        if items_size > MAX_ITEMS or result_size > MAX_RESULT:
            return _failure(identity, "result", "PRECHECK_RESULT_TOO_LARGE", status, code)
    except (ValueError, TypeError):
        return _failure(identity, "result", "PLATFORM_SCHEMA_INVALID", status, code)
    return ExecutionResult(status=ExecutionStatus.SUCCESS, result=result)
