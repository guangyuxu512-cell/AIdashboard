"""Product-specific Verify registry and controlled negative exit proofs."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "verify"
    / "product_data_contracts.py"
)
MUTATIONS = (
    "api-status",
    "dto-field",
    "metric-unit",
    "zero-missing",
    "amount-scale",
    "ratio-scale",
    "period-date",
)


def _run(tmp_path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = {
        key: os.environ[key]
        for key in ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP")
        if key in os.environ
    }
    environment["BACKEND_RUNTIME_ENVIRONMENT"] = "test"
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), *arguments],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_product_data_verify_registry_matches_actual_contract(tmp_path: Path) -> None:
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []


@pytest.mark.parametrize("mutation", MUTATIONS)
def test_product_data_verify_mutations_exit_nonzero(
    tmp_path: Path,
    mutation: str,
) -> None:
    result = _run(tmp_path, "--mutation", mutation)
    assert result.returncode == 1, result.stderr
    findings = json.loads(result.stdout)
    assert len(findings) == 1
    assert findings[0]["expected"] != findings[0]["actual"]
