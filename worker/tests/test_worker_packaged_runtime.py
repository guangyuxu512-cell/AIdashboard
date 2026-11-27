import os
from pathlib import Path
import subprocess
import sys


def test_runtime_import_check_does_not_start_or_configure_worker(tmp_path):
    worker_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["ECOMMERCE_WORKER_DATA_ROOT"] = str(tmp_path)
    if os.name != "nt":
        env["PYSTRAY_BACKEND"] = "dummy"
    result = subprocess.run(
        [sys.executable, "-m", "app", "--check-runtime-imports"],
        cwd=worker_root, env=env, capture_output=True, text=True, timeout=45,
    )
    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []
