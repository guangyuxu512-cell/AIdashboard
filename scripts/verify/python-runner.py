"""Run existing pytest in a credential-free cwd, or the bounded ASGI probe."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def envelope_probe():
    # Reuse the formal test application's dependency overrides, not DB/auth I/O.
    from tests.test_api_v1 import request
    from product_data_contracts import product_data_contract_observations
    observations = []
    for name, query in (
        ("missing_timezone", "occurrence_date=2026-08-24"),
        ("invalid_timezone", "occurrence_date=2026-08-24&view_timezone=Mars%2FOlympus"),
        ("normal_validation", "page=0"),
    ):
        response = request("GET", f"/api/v1/schedules?{query}")
        body = response.json()
        required = ["code", "message", "request_id"]
        observations.append({"rule": "error-envelope", "contract": f"schedules:{name}",
            "expected": {"status": 422, "required": required, "code": "VALIDATION_ERROR", "valid_details": True},
            "actual": {"status": response.status_code, "required": [key for key in required if isinstance(body.get(key), str) and body[key]],
                       "code": body.get("code"), "valid_details": body.get("details") is None or isinstance(body["details"], (dict, list))}})
    observations.extend(selection_brand_contract_observations())
    observations.extend(product_data_contract_observations())
    print(json.dumps([row for row in observations if row["expected"] != row["actual"]]))


def selection_brand_contract_observations():
    """Offline fixed expectations for current wire values and frozen readers.

    These expected values are deliberately independent of ``BRAND_TYPES`` and
    ``LEGACY_BRAND_TYPES_V7``.  Importing those constants as the expected side
    would let an implementation and its checker drift together.
    """

    from datetime import UTC, datetime
    from uuid import UUID

    from app.modules.product_selection.request_mapping import freeze_short_video_request
    from app.modules.product_selection.run_contract import (
        SelectionResolvedRequest,
        SelectionRunOriginal,
    )

    accepted_at = datetime(2026, 10, 18, 0, 0, tzinfo=UTC)
    shop_id = UUID("00000000-0000-0000-0000-000000000018")
    current_wire = {"all": "-1", "known": "1", "unknown": "0"}
    legacy_wire = {"known": "0", "unknown": "1"}

    def original(brand, rank_from=1, rank_to=10):
        return SelectionRunOriginal.model_validate({
            "shop_id": shop_id,
            "channel": "short-video",
            "period": "7d",
            "industry_id": "7",
            "category_ids": ["1000009092", "1000009142"],
            "brand": brand,
            "price_mode": "all",
            "first_listed_only": False,
            "rank_from": rank_from,
            "rank_to": rank_to,
        })

    rows = []
    for brand, expected_wire in current_wire.items():
        frozen = freeze_short_video_request(original(brand), accepted_at)
        rows.append({
            "rule": "selection-brand-wire",
            "contract": f"product-selection:brand:{brand}",
            "expected": {
                "brand_type": expected_wire,
                "version": 3 if brand == "all" else 9,
            },
            "actual": {
                "brand_type": frozen.scope.brand_type,
                "version": frozen.version,
            },
        })

    for version, rank in ((7, (1, 10)), (8, (150, 200))):
        for brand, expected_wire in legacy_wire.items():
            intent = original(brand, rank[0], rank[1])
            default = freeze_short_video_request(
                intent.model_copy(update={"brand": "all"}),
                accepted_at,
            )
            raw = default.model_dump(mode="json") | {"version": version}
            raw["original"]["brand"] = brand
            raw["scope"]["brand_type"] = expected_wire
            raw["date_plan"]["backup_scope"]["brand_type"] = expected_wire
            frozen = SelectionResolvedRequest.model_validate(raw)
            roundtrip = SelectionResolvedRequest.model_validate_json(
                frozen.model_dump_json(),
            )
            rows.append({
                "rule": "selection-brand-frozen-reader",
                "contract": f"product-selection:v{version}:{brand}",
                "expected": {
                    "brand_type": expected_wire,
                    "version": version,
                    "roundtrip": True,
                },
                "actual": {
                    "brand_type": roundtrip.scope.brand_type,
                    "version": roundtrip.version,
                    "roundtrip": roundtrip == frozen,
                },
            })
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("suite", choices=["backend", "worker", "probe"])
    args = parser.parse_args()
    # Never inherit deployment/provider configuration; do not read .env or Profile.
    for key in list(os.environ):
        if key.startswith(("BACKEND_", "WORKER_", "DOUYIN_", "PG", "DATABASE_")):
            del os.environ[key]
    os.environ["BACKEND_RUNTIME_ENVIRONMENT"] = "test"
    sys.path.insert(0, str(ROOT / "scripts" / "verify"))
    sys.path.insert(0, str(ROOT / ("backend" if args.suite == "probe" else args.suite)))
    previous = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="control-center-verify-python-") as temporary:
        try:
            os.chdir(temporary)
            if args.suite == "probe":
                envelope_probe()
            else:
                import pytest
                suite = ROOT / args.suite
                params = [str(suite / "tests"), "-c", str(suite / "pyproject.toml"), "--rootdir", str(suite)]
                if args.suite == "backend":
                    params += ["--ignore=" + str(suite / "tests/test_douyin_signer_runtime.py"),
                               "--ignore=" + str(suite / "tests/test_notification_webhook_e2e.py"),
                               "--ignore=" + str(suite / "tests/test_application_shop_session_postgres.py")]
                raise SystemExit(pytest.main(params))
        finally:
            # Windows cannot remove the current directory. Restore it before
            # TemporaryDirectory cleans only this newly created directory.
            os.chdir(previous)
