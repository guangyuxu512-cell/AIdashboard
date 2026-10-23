import json
from types import SimpleNamespace

from app.core.config import Settings
from app.modules.product_collection.cleaner import ExistingUuProductPackageCleaner


def test_cleaner_adapter_uses_current_price_evidence_and_preserves_zero():
    settings = Settings(
        product_collection_image_allowed_hosts=["img.example.test"],
    )
    adapter = ExistingUuProductPackageCleaner(settings)
    product_id = "3832497447662387684"
    raw = {
        "eventType": "complete",
        "detailBody": {},
        "skuBody": {},
        "capturedAt": 1792470000000,
        "taskContext": {
            "jobId": "job-a",
            "captureBatchId": "batch-a",
            "jobType": "product",
            "sourcePlatform": "douyin",
            "sourceProductId": product_id,
        },
    }
    result = {
        "productId": product_id,
        "capturedAt": 1792470000000,
        "category": {"levels": [{"id": "1", "name": "家居"}]},
        "clean": {
            "goodsInfo": {
                "goodsName": "零价测试商品",
                "goodsImageList": [
                    "https://img.example.test/a.webp?token=must-be-removed",
                ],
                "skuInfoMap": {
                    "sku-1": {
                        "extra_business_info": (
                            '{"first_price":{"left_price_num":0},'
                            '"second_price":{"left_price_num":1,"price_prefix":"券后价"}}'
                        ),
                        "aria_label_price": "￥0.00券后价￥0.01",
                    },
                },
            },
            "shopInfo": {"shopId": "merchant-1", "shopName": "测试店铺"},
        },
    }
    mapped = adapter._map_result(raw, result)
    assert mapped.current_sale_price_cent == 0
    assert mapped.currency == "CNY"
    assert mapped.price_evidence["values_cent"] == [0]
    assert mapped.primary_image_url == "https://img.example.test/a.webp"
    assert mapped.category_path == ("家居",)


def test_cleaner_adapter_keeps_price_unknown_without_evidence():
    settings = Settings()
    adapter = ExistingUuProductPackageCleaner(settings)
    product_id = "3832497447662387684"
    raw = {
        "capturedAt": 1792470000000,
        "taskContext": {
            "sourcePlatform": "douyin",
            "sourceProductId": product_id,
        },
    }
    mapped = adapter._map_result(
        raw,
        {
            "productId": product_id,
            "clean": {"goodsInfo": {"skuInfoMap": {}}, "shopInfo": {}},
        },
    )
    assert mapped.current_sale_price_cent is None
    assert mapped.currency is None
    assert mapped.price_evidence == {
        "state": "unknown",
        "source": None,
        "values_cent": [],
    }


def test_cleaner_does_not_truncate_fractional_cent_visible_price():
    adapter = ExistingUuProductPackageCleaner(Settings())
    product_id = "3832497447662387684"
    mapped = adapter._map_result(
        {
            "capturedAt": 1792470000000,
            "taskContext": {
                "sourcePlatform": "douyin",
                "sourceProductId": product_id,
            },
        },
        {
            "productId": product_id,
            "clean": {
                "goodsInfo": {
                    "skuInfoMap": {
                        "sku-1": {"aria_label_price": "￥1.999"},
                    },
                },
                "shopInfo": {},
            },
        },
    )
    assert mapped.current_sale_price_cent is None
    assert mapped.price_evidence["state"] == "unknown"


def test_cleaner_subprocess_does_not_inherit_backend_secrets(
    monkeypatch,
    tmp_path,
):
    module_path = tmp_path / "converter.mjs"
    module_path.write_text("export function convertCompletePackage() {}", encoding="utf-8")
    monkeypatch.setenv("BACKEND_DATABASE_URL", "postgresql://sensitive")
    monkeypatch.setenv("BACKEND_PRODUCT_COLLECTION_GATEWAY_CONTROL_TOKEN", "sensitive")
    monkeypatch.setenv(
        "BACKEND_PRODUCT_COLLECTION_INGEST_HMAC_KEY",
        "sensitive-hmac-key-material-32-bytes",
    )
    captured: dict[str, object] = {}

    def run(*_args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "productId": "3832497447662387684",
                    "capturedAt": 1792470000000,
                    "clean": {"goodsInfo": {}, "shopInfo": {}},
                },
            ),
        )

    from app.modules.product_collection import cleaner

    monkeypatch.setattr(cleaner.subprocess, "run", run)
    adapter = ExistingUuProductPackageCleaner(
        Settings(product_collection_cleaner_module_path=module_path),
    )
    adapter.convert(
        {
            "capturedAt": 1792470000000,
            "taskContext": {
                "sourcePlatform": "douyin",
                "sourceProductId": "3832497447662387684",
            },
        },
    )
    environment = {key.upper(): value for key, value in captured["env"].items()}
    assert "PATH" in environment
    assert "BACKEND_DATABASE_URL" not in environment
    assert "BACKEND_PRODUCT_COLLECTION_GATEWAY_CONTROL_TOKEN" not in environment
    assert "BACKEND_PRODUCT_COLLECTION_INGEST_HMAC_KEY" not in environment
