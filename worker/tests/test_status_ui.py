import json
from pathlib import Path

from app.status_ui import read_runtime_status


def test_tkinter_is_available_and_status_ui_reads_snapshot_only(
    tmp_path: Path,
) -> None:
    import tkinter

    assert tkinter.TkVersion > 0
    path = tmp_path / "runtime-status.json"
    path.write_text(
        json.dumps({"device_id": "device-a", "recent_events": []}),
        encoding="utf-8",
    )

    assert read_runtime_status(path)["device_id"] == "device-a"
    assert read_runtime_status(tmp_path / "missing.json") == {}
