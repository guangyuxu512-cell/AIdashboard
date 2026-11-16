"""Narrow adapter around the reviewed existing ``convertCompletePackage``."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

from app.core.config import Settings
from app.modules.product_collection.contracts import SourcePlatform
from app.modules.product_collection.payload import sanitize_image_url
from app.modules.product_collection.ports import CleanedProductPackage


_VISIBLE_PRICE = re.compile(r"[￥¥](\d+(?:\.\d+)?)")
_CLEANER_ENVIRONMENT_KEYS = frozenset(
    {
        "COMSPEC",
        "LANG",
        "LC_ALL",
        "PATH",
        "PATHEXT",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TZ",
        "WINDIR",
    },
)


class ExistingUuProductPackageCleaner:
    """Execute the already-reviewed JS cleaner without copying its code.

    The module path is deployment configuration, never a value from an upload.
    No output directory is supplied, so the converter cannot publish files or
    connect to the central database through this adapter.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def convert(self, raw_package: dict[str, Any]) -> CleanedProductPackage:
        module_path = self.settings.product_collection_cleaner_module_path
        if module_path is None:
            raise RuntimeError("Product collection cleaner module is not configured")
        resolved_module = module_path.expanduser().resolve(strict=True)
        if not resolved_module.is_file() or resolved_module.suffix.lower() != ".mjs":
            raise RuntimeError("Product collection cleaner module is invalid")
        runner = Path(__file__).with_name("cleaner_runner.mjs").resolve(strict=True)
        payload = json.dumps(
            raw_package,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        completed = subprocess.run(
            [
                self.settings.product_collection_cleaner_node_executable,
                str(runner),
                str(resolved_module),
            ],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            env=_cleaner_environment(),
            timeout=self.settings.product_collection_cleaner_timeout_seconds,
            check=False,
        )
        if completed.returncode != 0 or not completed.stdout:
            raise RuntimeError("Product collection cleaner rejected the complete package")
        try:
            result = json.loads(completed.stdout)
        except (TypeError, json.JSONDecodeError) as error:
            raise RuntimeError("Product collection cleaner returned invalid output") from error
        return self._map_result(raw_package, result)

    def _map_result(
        self,
        raw_package: dict[str, Any],
        result: Any,
    ) -> CleanedProductPackage:
        if not isinstance(result, dict) or not isinstance(result.get("clean"), dict):
            raise RuntimeError("Product collection cleaner returned invalid output")
        context = raw_package.get("taskContext")
        if not isinstance(context, dict):
            raise RuntimeError("Complete package task context is unavailable")
        product_id = _string(result.get("productId"), 128)
        expected_id = _string(context.get("sourceProductId"), 128)
        if product_id is None or product_id != expected_id:
            raise RuntimeError("Product collection cleaner identity mismatch")
        platform = SourcePlatform(_string(context.get("sourcePlatform"), 32))
        clean = result["clean"]
        goods_info = clean.get("goodsInfo") if isinstance(clean.get("goodsInfo"), dict) else {}
        shop_info = clean.get("shopInfo") if isinstance(clean.get("shopInfo"), dict) else {}
        title = _string(goods_info.get("goodsName"), 10000)
        merchant_id = _string(shop_info.get("shopId"), 500)
        merchant_name = _string(shop_info.get("shopName"), 2000)
        merchant = (
            {"source_id": merchant_id, "display_name": merchant_name}
            if merchant_id is not None or merchant_name is not None
            else None
        )
        category_path = _category_path(result.get("category"))
        price, price_evidence = _current_price(clean)
        image_url = _primary_image(
            goods_info,
            frozenset(host.lower() for host in self.settings.product_collection_image_allowed_hosts),
        )
        captured_at = _captured_at(result.get("capturedAt"), raw_package.get("capturedAt"))
        return CleanedProductPackage(
            source_platform=platform,
            source_product_id=product_id,
            captured_at=captured_at,
            source_format_version=1,
            cleaner_version=self.settings.product_collection_cleaner_version,
            title=title,
            source_url=None,
            primary_image_url=image_url,
            merchant_snapshot=merchant,
            category_path=category_path,
            current_sale_price_cent=price,
            currency="CNY" if price is not None else None,
            uu_snapshot=clean,
            price_evidence=price_evidence,
        )


def _cleaner_environment() -> dict[str, str]:
    """Pass only process-launch essentials, never Backend service secrets."""

    return {
        key: value
        for key, value in os.environ.items()
        if key.upper() in _CLEANER_ENVIRONMENT_KEYS
    }


def _string(value: Any, maximum: int) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result[:maximum] if result else None


def _captured_at(*values: Any) -> datetime:
    for value in values:
        if isinstance(value, bool):
            continue
        try:
            milliseconds = int(value)
        except (TypeError, ValueError):
            continue
        if milliseconds >= 0:
            return datetime.fromtimestamp(milliseconds / 1000, tz=UTC)
    raise RuntimeError("Complete package capture time is invalid")


def _category_path(value: Any) -> tuple[str, ...] | None:
    if not isinstance(value, dict) or not isinstance(value.get("levels"), list):
        return None
    names = []
    for item in value["levels"][:8]:
        if isinstance(item, dict):
            name = _string(item.get("name"), 120)
            if name is not None:
                names.append(name)
    return tuple(names) or None


def _current_price(clean: dict[str, Any]) -> tuple[int | None, dict[str, Any]]:
    goods = clean.get("goodsInfo")
    sku_map = goods.get("skuInfoMap") if isinstance(goods, dict) else None
    values: list[int] = []
    if isinstance(sku_map, dict):
        for sku in sku_map.values():
            if not isinstance(sku, dict):
                continue
            business = sku.get("extra_business_info")
            if isinstance(business, str):
                try:
                    business = json.loads(business)
                except json.JSONDecodeError:
                    business = None
            left = None
            if isinstance(business, dict) and isinstance(business.get("first_price"), dict):
                left = business["first_price"].get("left_price_num")
            cents = _non_negative_integer(left)
            if cents is None:
                match = _VISIBLE_PRICE.search(str(sku.get("aria_label_price") or ""))
                if match is not None:
                    cents = _non_negative_integer(Decimal(match.group(1)) * 100)
            if cents is not None:
                values.append(cents)
    if not values:
        return None, {"state": "unknown", "source": None, "values_cent": []}
    return min(values), {
        "state": "available",
        "source": "clean.goodsInfo.skuInfoMap.current_visible_price",
        "values_cent": values,
    }


def _non_negative_integer(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not decimal.is_finite() or decimal < 0 or decimal != decimal.to_integral_value():
        return None
    return int(decimal)


def _primary_image(goods_info: dict[str, Any], hosts: frozenset[str]) -> str | None:
    images = goods_info.get("goodsImageList")
    if not hosts or not isinstance(images, list):
        return None
    for value in images:
        if not isinstance(value, str):
            continue
        try:
            return sanitize_image_url(value, allowed_hosts=hosts)
        except ValueError:
            continue
    return None
