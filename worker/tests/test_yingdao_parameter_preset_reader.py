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
        json.dumps({"格式版本": 1, "公共参数": {"标题": "公共"}, "店铺参数": {"shop-a": {"标题": "店铺 A", "数量": 0}}}, ensure_ascii=False),
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


def test_reader_resolves_a_single_account_without_falling_back_for_many(
    tmp_path: Path,
) -> None:
    reader = _load_reader()
    params_path = tmp_path / "params.json"
    account_path = tmp_path / "account.json"
    params_path.write_text(
        json.dumps(
            {
                "格式版本": 1,
                "公共参数": {"页码": 1},
                "店铺参数": {"shop-a": {"页码": 2}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    account_path.write_text(
        json.dumps({"店铺列表": [{"店铺ID": "shop-a"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    assert reader.read_yingdao_parameters(
        params_path,
        account_json_path=account_path,
    ) == {"页码": 2}

    account_path.write_text(
        json.dumps(
            {"店铺列表": [{"店铺ID": "shop-a"}, {"店铺ID": "shop-b"}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="当前店铺ID"):
        reader.read_yingdao_parameters(params_path, account_json_path=account_path)
