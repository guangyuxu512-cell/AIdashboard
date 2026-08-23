import subprocess
import sys

import pytest

from app.shared import subprocesses


def test_windows_noninteractive_command_adds_no_window_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        captured.update(kwargs)
        return subprocess.CompletedProcess(args, 7, stdout="out", stderr="err")

    monkeypatch.setattr(subprocesses, "_IS_WINDOWS", True)
    monkeypatch.setattr(subprocesses.subprocess, "run", fake_run)

    result = subprocesses.run_noninteractive_command(
        ["tasklist.exe"],
        capture_output=True,
        text=True,
    )

    assert int(captured["creationflags"]) & subprocesses._CREATE_NO_WINDOW
    assert captured["shell"] is False
    assert captured["capture_output"] is True
    assert result.returncode == 7
    assert result.stdout == "out"
    assert result.stderr == "err"


def test_non_windows_command_does_not_pass_windows_creation_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocesses, "_IS_WINDOWS", False)
    monkeypatch.setattr(subprocesses.subprocess, "run", fake_run)

    subprocesses.run_noninteractive_command(["true"])

    assert "creationflags" not in captured
    assert captured["shell"] is False


def test_noninteractive_command_still_captures_output_and_return_code() -> None:
    result = subprocesses.run_noninteractive_command(
        [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(4)"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 4
    assert result.stdout.strip() == "out"
    assert result.stderr.strip() == "err"
