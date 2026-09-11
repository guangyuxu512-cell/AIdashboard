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

    version = payload.get("format_version")
    if version is None:
        return dict(payload)
    if version != PARAMETER_PRESET_FORMAT_VERSION:
        raise ValueError(f"不支持的参数预设格式版本: {version!r}")

    common = _object_field(payload, "common_parameters")
    if shop_id is None:
        return common
    shop_parameters = _object_field(payload, "shop_parameters")
    selected = shop_parameters.get(str(shop_id))
    if not isinstance(selected, Mapping):
        raise ValueError(f"当前任务未下发店铺 {shop_id} 的参数")
    return dict(selected)


def _object_field(payload: Mapping[str, Any], name: str) -> dict[str, Any]:
    value = payload.get(name)
    if not isinstance(value, Mapping):
        raise ValueError(f"参数预设缺少 Object 字段: {name}")
    return dict(value)
