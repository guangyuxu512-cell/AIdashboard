"""Credential-free Product Data contract observations with fixed expectations."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from inspect import signature
import json
from typing import get_args
from uuid import UUID


EXPECTED_ROUTES = [
    {
        "path": "/api/v1/product-data",
        "method": "GET",
        "status": 200,
        "request_model": None,
        "response_model": "ProductDataListRead",
    },
    {
        "path": "/api/v1/product-data/collection-batches",
        "method": "POST",
        "status": 202,
        "request_model": "ProductDataCollectionBatchRequest",
        "response_model": "ProductDataCollectionBatchRead",
    },
    {
        "path": "/api/v1/product-data/collection-batches/{collection_batch_id}",
        "method": "GET",
        "status": 200,
        "request_model": None,
        "response_model": "ProductDataCollectionBatchRead",
    },
    {
        "path": "/api/v1/product-data/collection-shops",
        "method": "GET",
        "status": 200,
        "request_model": None,
        "response_model": "list",
    },
    {
        "path": "/api/v1/product-data/collections",
        "method": "POST",
        "status": 202,
        "request_model": "ProductDataCollectionRequest",
        "response_model": "ProductDataGenerationRead",
    },
    {
        "path": "/api/v1/product-data/collections/{generation_id}",
        "method": "GET",
        "status": 200,
        "request_model": None,
        "response_model": "ProductDataGenerationRead",
    },
]

EXPECTED_DTOS = {
    "ProductDataQuery": [
        "period",
        "start_date",
        "end_date",
        "shop_id",
        "product_id",
        "product_name",
        "sale_type",
        "content_type",
        "ranges",
        "page",
        "page_size",
        "sort_field",
        "sort_direction",
    ],
    "ProductDataCollectionRequest": [
        "shop_id",
        "period",
        "submission_key",
        "sale_type",
        "content_type",
    ],
    "ProductDataCollectionBatchRequest": [
        "shop_ids",
        "period",
        "submission_key",
        "sale_type",
        "content_type",
    ],
    "ProductDataMetricRead": [
        "state",
        "raw_value",
        "raw_unit",
        "unit_verified",
    ],
    "ProductDataRowRead": [
        "shop_product_id",
        "generation_id",
        "shop_id",
        "shop_name",
        "product_id",
        "title",
        "image_url",
        "metrics",
        "scope",
        "retrieved_at",
    ],
    "ProductDataGenerationRead": [
        "generation_id",
        "scope",
        "status",
        "stage",
        "received_pages",
        "expected_total",
        "received_total",
        "pages_complete",
        "raw_complete_rows",
        "unit_complete_rows",
        "failure_code",
        "attempt_count",
        "last_heartbeat_at",
        "created_at",
        "started_at",
        "finished_at",
        "published_at",
        "lease_expired",
    ],
    "ProductDataCollectionItemRead": [
        "shop_id",
        "shop_name",
        "generation",
    ],
    "ProductDataCollectionBatchRead": [
        "collection_batch_id",
        "status",
        "total_count",
        "pending_count",
        "running_count",
        "succeeded_count",
        "failed_count",
        "created_at",
        "items",
    ],
    "ProductDataCollectionShopRead": [
        "shop_id",
        "shop_name",
    ],
}

EXPECTED_GENERATION_STATUSES = ["pending", "running", "succeeded", "failed"]
EXPECTED_OBSERVATION_STATES = ["available", "missing", "null", "invalid"]
EXPECTED_METRICS = [
    ["product_show_cnt", "count", 5],
    ["product_click_cnt", "count", 5],
    ["product_show_click_converse_uv_rate", "ratio", 4],
    ["click_add_to_cart_uv", "count", 5],
    ["product_add_show_converse_uv_ratio", "ratio", 4],
    ["net_pay_cnt", "count", 5],
    ["pay_cnt_exclude_refund", "count", 5],
    ["product_click_pay_converse_uv_rate", "ratio", 4],
    ["pay_refund_ratio", "ratio", 4],
    ["pay_amt", "amount", 3],
    ["pay_cnt", "count", 5],
    ["pay_ucnt", "count", 5],
    ["per_user_price", "amount", 3],
    ["pay_refund_success_amt", "amount", 3],
    ["pay_refund_success_order_cnt", "count", 5],
    ["product_show_ucnt", "count", 5],
    ["product_click_ucnt", "count", 5],
]

EXPECTED_WINDOWS = {
    "1d": {
        "start_date": "2026-10-17",
        "end_date": "2026-10-17",
        "date_type": "20",
        "begin_date": "2026/10/17 00:00:00",
        "end_query": "2026/10/17 00:00:00",
    },
    "7d": {
        "start_date": "2026-10-11",
        "end_date": "2026-10-17",
        "date_type": "21",
        "begin_date": "2026/10/11 00:00:00",
        "end_query": "2026/10/17 00:00:00",
    },
    "30d": {
        "start_date": "2026-09-18",
        "end_date": "2026-10-17",
        "date_type": "23",
        "begin_date": "2026/09/18 00:00:00",
        "end_query": "2026/10/17 00:00:00",
    },
}


def _observation(rule: str, contract: str, expected, actual) -> dict:
    return {
        "rule": rule,
        "contract": contract,
        "expected": expected,
        "actual": actual,
    }


def _payload(product_metrics) -> dict:
    info = {
        "product_id_value": {"value": {"unit": 1, "value_str": "9000000000000000001"}},
        "shop_id_value": {"value": {"unit": 1, "value_str": "999999999"}},
        "product_name_value": {"value": {"unit": 1, "value_str": "Synthetic product"}},
        "product_image_value": {
            "value": {"unit": 1, "value_str": "https://example.test/product.png"},
        },
    }
    cell = {"product_info": info}
    for definition in product_metrics:
        cell[definition.code] = {
            definition.code + "_index_values": {
                "index_values": {
                    "value": {"unit": definition.observed_unit, "value": 0},
                },
            },
        }
    return {
        "st": 0,
        "data": [{"cell_info": cell}],
        "meta": [],
        "page_result": {"page_no": 1, "page_size": 10, "total": 1},
    }


def _current(raw: dict, code: str) -> dict:
    return raw["data"][0]["cell_info"][code][code + "_index_values"][
        "index_values"
    ]["value"]


def product_data_contract_observations() -> list[dict]:
    """Read actual declarations and behavior; expected values stay local."""

    from app.modules.product_data.api import router
    from app.modules.product_data.schemas import (
        ProductDataCollectionBatchRead,
        ProductDataCollectionBatchRequest,
        ProductDataCollectionItemRead,
        ProductDataCollectionRequest,
        ProductDataCollectionShopRead,
        ProductDataGenerationRead,
        ProductDataMetricRead,
        ProductDataQuery,
        ProductDataRowRead,
    )
    from app.modules.product_data.source import freeze_native_slice
    from app.platforms.douyin.product_data import (
        PRODUCT_METRICS,
        ObservationState,
        parse_compass_product_data_page,
    )

    routes = []
    for route in router.routes:
        body_field = getattr(route, "body_field", None)
        body_name = getattr(body_field, "name", None)
        request_model = (
            signature(route.endpoint).parameters[body_name].annotation
            if body_name is not None
            else None
        )
        response_model = getattr(route, "response_model", None)
        for method in sorted(getattr(route, "methods", ())):
            routes.append(
                {
                    "path": route.path,
                    "method": method,
                    "status": route.status_code or 200,
                    "request_model": getattr(request_model, "__name__", None),
                    "response_model": getattr(response_model, "__name__", None),
                },
            )
    routes.sort(key=lambda row: (row["path"], row["method"]))
    expected_routes = sorted(
        EXPECTED_ROUTES,
        key=lambda row: (row["path"], row["method"]),
    )

    dto_types = (
        ProductDataQuery,
        ProductDataCollectionRequest,
        ProductDataCollectionBatchRequest,
        ProductDataMetricRead,
        ProductDataRowRead,
        ProductDataGenerationRead,
        ProductDataCollectionItemRead,
        ProductDataCollectionBatchRead,
        ProductDataCollectionShopRead,
    )
    dto_fields = {model.__name__: list(model.model_fields) for model in dto_types}
    generation_statuses = list(
        get_args(ProductDataGenerationRead.model_fields["status"].annotation),
    )
    observation_states = list(get_args(ObservationState))
    metrics = [
        [definition.code, definition.kind, definition.observed_unit]
        for definition in PRODUCT_METRICS
    ]

    query = ProductDataQuery(
        period="1d",
        start_date=date(2026, 10, 17),
        end_date=date(2026, 10, 17),
    )
    query_defaults = {
        "page": query.page,
        "page_size": query.page_size,
        "page_size_100_accepted": ProductDataQuery(
            period="1d",
            start_date=date(2026, 10, 17),
            end_date=date(2026, 10, 17),
            page_size=100,
        ).page_size,
        "sale_type": query.sale_type,
        "content_type": query.content_type,
    }

    zero_raw = _payload(PRODUCT_METRICS)
    zero_row = parse_compass_product_data_page(
        zero_raw,
        expected_platform_shop_id="999999999",
        expected_page_no=1,
    ).products[0]
    zero = zero_row.metric("pay_cnt")

    states_raw = _payload(PRODUCT_METRICS)
    states_cell = states_raw["data"][0]["cell_info"]
    del states_cell["product_show_cnt"]
    _current(states_raw, "product_click_cnt")["value"] = None
    states_cell["net_pay_cnt"] = []
    states_row = parse_compass_product_data_page(
        states_raw,
        expected_platform_shop_id="999999999",
        expected_page_no=1,
    ).products[0]
    state_semantics = {
        "zero": {
            "state": zero.state,
            "raw_value": str(zero.raw_value),
            "display_value": str(zero.display_value),
        },
        "missing": states_row.metric("product_show_cnt").state,
        "null": states_row.metric("product_click_cnt").state,
        "invalid": states_row.metric("net_pay_cnt").state,
    }

    scale_raw = _payload(PRODUCT_METRICS)
    _current(scale_raw, "pay_amt")["value"] = Decimal(
        "12345678901234567890.1234567890123456789",
    )
    _current(scale_raw, "pay_refund_ratio")["value"] = Decimal(
        "0.12345678901234567890123456789",
    )
    _current(scale_raw, "pay_cnt")["value"] = 900719925474099312345
    scale_row = parse_compass_product_data_page(
        scale_raw,
        expected_platform_shop_id="999999999",
        expected_page_no=1,
    ).products[0]
    scales = {
        "amount_raw": str(scale_row.metric("pay_amt").raw_value),
        "amount_display": str(scale_row.metric("pay_amt").display_value),
        "ratio_raw": str(scale_row.metric("pay_refund_ratio").raw_value),
        "ratio_display": str(scale_row.metric("pay_refund_ratio").display_value),
        "count_display": str(scale_row.metric("pay_cnt").display_value),
    }

    accepted_at = datetime.fromisoformat("2026-10-18T00:30:00+08:00")
    windows = {}
    for period in ("1d", "7d", "30d"):
        scope = freeze_native_slice(
            UUID("00000000-0000-0000-0000-000000000018"),
            period,
            accepted_at,
        )
        business_query = scope.business_query(1)
        windows[period] = {
            "start_date": scope.start_date.isoformat(),
            "end_date": scope.end_date.isoformat(),
            "date_type": scope.date_type,
            "begin_date": business_query["begin_date"],
            "end_query": business_query["end_date"],
        }

    return [
        _observation("product-data-api", "product-data:routes", expected_routes, routes),
        _observation("product-data-dto", "product-data:dto-fields", EXPECTED_DTOS, dto_fields),
        _observation(
            "product-data-status",
            "product-data:generation-status",
            EXPECTED_GENERATION_STATUSES,
            generation_statuses,
        ),
        _observation(
            "product-data-status",
            "product-data:observation-state",
            EXPECTED_OBSERVATION_STATES,
            observation_states,
        ),
        _observation(
            "product-data-query",
            "product-data:query-defaults",
            {
                "page": 1,
                "page_size": 20,
                "page_size_100_accepted": 100,
                "sale_type": "1",
                "content_type": "1",
            },
            query_defaults,
        ),
        _observation("product-data-metrics", "product-data:core17", EXPECTED_METRICS, metrics),
        _observation(
            "product-data-observation",
            "product-data:zero-missing-null-invalid",
            {
                "zero": {
                    "state": "available",
                    "raw_value": "0",
                    "display_value": "0",
                },
                "missing": "missing",
                "null": "null",
                "invalid": "invalid",
            },
            state_semantics,
        ),
        _observation(
            "product-data-scale",
            "product-data:exact-amount-ratio-count",
            {
                "amount_raw": "12345678901234567890.1234567890123456789",
                "amount_display": "123456789012345678.901234567890123456789",
                "ratio_raw": "0.12345678901234567890123456789",
                "ratio_display": "0.12345678901234567890123456789",
                "count_display": "900719925474099312345",
            },
            scales,
        ),
        _observation(
            "product-data-period",
            "product-data:frozen-native-windows",
            EXPECTED_WINDOWS,
            windows,
        ),
    ]


def mutated_product_data_contract_observations(mutation: str) -> list[dict]:
    """Return a controlled bad actual side for negative verifier proofs."""

    rows = deepcopy(product_data_contract_observations())
    targets = {
        "api-status": ("product-data:routes", lambda actual: actual.__setitem__(0, actual[0] | {"status": 201})),
        "dto-field": ("product-data:dto-fields", lambda actual: actual["ProductDataRowRead"].pop()),
        "metric-unit": ("product-data:core17", lambda actual: actual[0].__setitem__(2, 4)),
        "zero-missing": (
            "product-data:zero-missing-null-invalid",
            lambda actual: actual["zero"].__setitem__("state", "missing"),
        ),
        "amount-scale": (
            "product-data:exact-amount-ratio-count",
            lambda actual: actual.__setitem__("amount_display", actual["amount_raw"]),
        ),
        "ratio-scale": (
            "product-data:exact-amount-ratio-count",
            lambda actual: actual.__setitem__("ratio_display", "12.345678901234567890123456789"),
        ),
        "period-date": (
            "product-data:frozen-native-windows",
            lambda actual: actual["7d"].__setitem__("start_date", "2026-10-12"),
        ),
    }
    contract, change = targets[mutation]
    row = next(item for item in rows if item["contract"] == contract)
    change(row["actual"])
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mutation",
        choices=[
            "api-status",
            "dto-field",
            "metric-unit",
            "zero-missing",
            "amount-scale",
            "ratio-scale",
            "period-date",
        ],
    )
    arguments = parser.parse_args()
    observations = (
        mutated_product_data_contract_observations(arguments.mutation)
        if arguments.mutation
        else product_data_contract_observations()
    )
    findings = [row for row in observations if row["expected"] != row["actual"]]
    print(json.dumps(findings, ensure_ascii=False))
    raise SystemExit(1 if findings else 0)
