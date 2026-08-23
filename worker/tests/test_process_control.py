import json
import os
import sys
from pathlib import Path
from uuid import uuid4

from app.process_control import (
    WorkerProcessController,
    WorkerProcessState,
    build_worker_core_command,
)
from app.shared.subprocesses import windows_no_window_creation_flags


def test_core_command_is_a_distinct_background_entrypoint() -> None:
    command = build_worker_core_command()
    assert command[0] == sys.executable
    assert command[-1] == "--worker-core"
    if os.name == "nt":
        assert windows_no_window_creation_flags() != 0


def test_core_owns_a_token_free_process_state_file(tmp_path: Path) -> None:
    device_id = uuid4()
    controller = WorkerProcessController(tmp_path)

    with WorkerProcessState(device_id, tmp_path):
        state = controller.running()
        assert state is not None
        assert state.device_id == device_id
        payload = json.loads(controller.state_path.read_text(encoding="utf-8"))
        assert "token" not in payload

    assert controller.state_path.exists() is False
