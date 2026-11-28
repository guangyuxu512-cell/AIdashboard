"""Small atomic, per-user configuration and status files."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def data_root() -> Path:
    return Path(os.environ.get("SIYU_GUARD_DATA_ROOT") or
                Path(os.environ.get("LOCALAPPDATA", ".")) / "SiyuWatchdog").resolve()


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".guard-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def load_config(root: Path) -> dict:
    result = read_json(root / "config.json", {})
    if not isinstance(result, dict) or not isinstance(result.get("items"), list):
        return {"items": []}
    return result
