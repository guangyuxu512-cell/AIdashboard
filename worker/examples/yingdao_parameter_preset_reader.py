"""Read a Backend-materialized Yingdao parameter preset from ``params.json``.

Copy this small helper into a Yingdao application's own Python code when that
application consumes the versioned preset payload.  It is intentionally not a
Worker Business Skill and does not access Worker configuration, accounts or
credentials.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


PARAMETER_PRESET_FORMAT_VERSION = 1


def read_yingdao_parameters(
    params_json_path: str | Path,
    *,
    account_json_path: str | Path | None = None,
    shop_id: str | None = None,
) -> dict[str, Any]:
    """Return effective parameters for one Shop or the shared parameters.

    Existing manual application Tasks still write their flat parameter object
    and are returned unchanged.  A preset envelope must already contain the
    fully merged selected-Shop values; this reader never merges or loads a
    preset itself.
    """

    payload = json.loads(Path(params_json_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("params.json 根对象必须是 JSON Object")

    version = payload.get("格式版本")
    if version is None:
        return dict(payload)
    if version != PARAMETER_PRESET_FORMAT_VERSION:
        raise ValueError(f"不支持的参数预设格式版本: {version!r}")

    common = _object_field(payload, "公共参数")
    if shop_id is None and account_json_path is not None:
        shop_id = _single_account_shop_id(account_json_path)
    if shop_id is None:
        return common
    shop_parameters = _object_field(payload, "店铺参数")
    selected = shop_parameters.get(str(shop_id))
    if not isinstance(selected, Mapping):
        raise ValueError(f"当前任务未下发店铺 {shop_id} 的参数")
    return dict(selected)


def _object_field(payload: Mapping[str, Any], name: str) -> dict[str, Any]:
    value = payload.get(name)
    if not isinstance(value, Mapping):
        raise ValueError(f"参数预设缺少 Object 字段: {name}")
    return dict(value)


def _single_account_shop_id(account_json_path: str | Path) -> str:
    """Read the explicitly current Shop from the official local account file.

    The Worker contract contains an ordered ``店铺列表`` rather than a hidden
    global current-shop state.  A single-Shop Task can therefore be resolved
    directly.  A multi-Shop application must pass the selected record's
    ``店铺ID`` explicitly; silently choosing the first account would leak the
    wrong Shop's parameters into the RPA flow.
    """

    account_payload = json.loads(Path(account_json_path).read_text(encoding="utf-8"))
    if not isinstance(account_payload, Mapping):
        raise ValueError("account.json 根对象必须是 JSON Object")
    shops = account_payload.get("店铺列表")
    if not isinstance(shops, list):
        raise ValueError("account.json 缺少店铺列表")
    if len(shops) != 1 or not isinstance(shops[0], Mapping):
        raise ValueError("多店铺任务必须传入当前店铺ID")
    shop_id = shops[0].get("店铺ID")
    if not isinstance(shop_id, str) or not shop_id:
        raise ValueError("account.json 当前店铺缺少店铺ID")
    return shop_id
