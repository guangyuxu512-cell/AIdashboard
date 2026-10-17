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
    print(json.dumps([row for row in observations if row["expected"] != row["actual"]]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("suite", choices=["backend", "worker", "probe"])
    args = parser.parse_args()
    # Never inherit deployment/provider configuration; do not read .env or Profile.
    for key in list(os.environ):
        if key.startswith(("BACKEND_", "WORKER_", "DOUYIN_", "PG", "DATABASE_")):
            del os.environ[key]
    os.environ["BACKEND_RUNTIME_ENVIRONMENT"] = "test"
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
                               "--ignore=" + str(suite / "tests/test_notification_webhook_e2e.py")]
                raise SystemExit(pytest.main(params))
        finally:
            # Windows cannot remove the current directory. Restore it before
            # TemporaryDirectory cleans only this newly created directory.
            os.chdir(previous)
