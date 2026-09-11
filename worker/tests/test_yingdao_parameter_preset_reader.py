import importlib.util
import json
from pathlib import Path

import pytest


def _load_reader() -> object:
    path = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "yingdao_parameter_preset_reader.py"
    )
    spec = importlib.util.spec_from_file_location("yingdao_preset_reader", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reader_supports_legacy_flat_and_materialized_shop_parameters(
    tmp_path: Path,
) -> None:
    reader = _load_reader()
    params_path = tmp_path / "params.json"
    params_path.write_text(
        json.dumps({"format_version": 1, "common_parameters": {"标题": "公共"}, "shop_parameters": {"shop-a": {"标题": "店铺 A", "数量": 0}}}, ensure_ascii=False),
        encoding="utf-8",
    )

    assert reader.read_yingdao_parameters(params_path, shop_id="shop-a") == {
        "标题": "店铺 A",
        "数量": 0,
    }
    assert reader.read_yingdao_parameters(params_path) == {"标题": "公共"}
    with pytest.raises(ValueError, match="shop-missing"):
        reader.read_yingdao_parameters(params_path, shop_id="shop-missing")

    params_path.write_text('{"旧参数": false}', encoding="utf-8")
    assert reader.read_yingdao_parameters(params_path, shop_id="shop-a") == {
        "旧参数": False,
    }
