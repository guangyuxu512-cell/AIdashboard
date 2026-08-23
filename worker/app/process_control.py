import ctypes
import json
import os
import subprocess
import sys
import time
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from app.local_config import get_worker_data_root, write_json_atomic
from app.shared.subprocesses import windows_no_window_creation_flags


@dataclass(frozen=True)
class WorkerProcessInfo:
    pid: int
    started_at_utc: datetime
    executable_path: Path
    device_id: UUID


class WorkerProcessState(AbstractContextManager["WorkerProcessState"]):
    def __init__(self, device_id: UUID, data_root: Path | None = None) -> None:
        self.path = (data_root or get_worker_data_root()) / "worker-state.json"
        executable_path, started_at = _current_process_identity()
        self.info = WorkerProcessInfo(
            pid=os.getpid(),
            started_at_utc=started_at,
            executable_path=executable_path,
            device_id=device_id,
        )

    def __enter__(self) -> "WorkerProcessState":
        write_json_atomic(
            self.path,
            {
                "pid": self.info.pid,
                "started_at_utc": self.info.started_at_utc.isoformat(),
                "executable_path": str(self.info.executable_path),
                "device_id": str(self.info.device_id),
            },
        )
        return self

    def __exit__(self, *args: object) -> None:
        current = read_worker_process_state(self.path)
        if current is not None and current.pid == self.info.pid:
            self.path.unlink(missing_ok=True)


class WorkerProcessController:
    def __init__(self, data_root: Path | None = None) -> None:
        self.data_root = (data_root or get_worker_data_root()).resolve()
        self.state_path = self.data_root / "worker-state.json"
        self.log_directory = self.data_root / "logs"

    def running(self) -> WorkerProcessInfo | None:
        state = read_worker_process_state(self.state_path)
        if state is None:
            return None
        if not _matches_running_process(state):
            self.state_path.unlink(missing_ok=True)
            return None
        return state

    def start(self) -> WorkerProcessInfo | None:
        existing = self.running()
        if existing is not None:
            return existing
        self.log_directory.mkdir(parents=True, exist_ok=True)
        with (
            (self.log_directory / "bootstrap.out.log").open(
                "a",
                encoding="utf-8",
            ) as stdout,
            (self.log_directory / "bootstrap.err.log").open(
                "a",
                encoding="utf-8",
            ) as stderr,
        ):
            subprocess.Popen(
                build_worker_core_command(),
                cwd=str(_worker_working_directory()),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                creationflags=windows_no_window_creation_flags(),
                close_fds=True,
            )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            running = self.running()
            if running is not None:
                return running
            time.sleep(0.1)
        return None

    def restart(self) -> WorkerProcessInfo | None:
        self.stop()
        return self.start()

    def stop(self) -> bool:
        state = self.running()
        if state is None:
            return True
        if os.name == "nt":
            _terminate_windows_process(state.pid)
        else:
            os.kill(state.pid, 15)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if not _matches_running_process(state):
                self.state_path.unlink(missing_ok=True)
                return True
            time.sleep(0.1)
        return False


def build_worker_core_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--worker-core"]
    return [sys.executable, "-m", "app", "--worker-core"]


def read_worker_process_state(path: Path) -> WorkerProcessInfo | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return WorkerProcessInfo(
            pid=int(payload["pid"]),
            started_at_utc=datetime.fromisoformat(str(payload["started_at_utc"])),
            executable_path=Path(str(payload["executable_path"])).resolve(),
            device_id=UUID(str(payload["device_id"])),
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def _worker_working_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _matches_running_process(state: WorkerProcessInfo) -> bool:
    if os.name != "nt":
        try:
            os.kill(state.pid, 0)
            return True
        except OSError:
            return False
    try:
        path, started_at = _inspect_windows_process(state.pid)
    except OSError:
        return False
    return (
        path == state.executable_path
        and abs((started_at - state.started_at_utc).total_seconds()) < 2
    )


def _inspect_windows_process(pid: int) -> tuple[Path, datetime]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.QueryFullProcessImageNameW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_ulong),
    ]
    kernel32.QueryFullProcessImageNameW.restype = ctypes.c_bool
    kernel32.GetProcessTimes.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    kernel32.GetProcessTimes.restype = ctypes.c_bool
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_bool
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        raise OSError(ctypes.get_last_error(), "Cannot inspect Worker process")
    try:
        size = ctypes.c_ulong(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(
            handle,
            0,
            buffer,
            ctypes.byref(size),
        ):
            raise OSError(ctypes.get_last_error(), "Cannot read Worker path")
        created = ctypes.c_ulonglong()
        exited = ctypes.c_ulonglong()
        kernel = ctypes.c_ulonglong()
        user = ctypes.c_ulonglong()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            raise OSError(ctypes.get_last_error(), "Cannot read Worker start time")
        return Path(buffer.value).resolve(), _filetime_to_datetime(created.value)
    finally:
        kernel32.CloseHandle(handle)


def _current_process_identity() -> tuple[Path, datetime]:
    if os.name != "nt":
        return Path(sys.executable).resolve(), datetime.now(UTC)
    return _inspect_windows_process(os.getpid())


def _filetime_to_datetime(value: int) -> datetime:
    return datetime(1601, 1, 1, tzinfo=UTC) + timedelta(microseconds=value / 10)


def _terminate_windows_process(pid: int) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.TerminateProcess.restype = ctypes.c_bool
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_bool
    handle = kernel32.OpenProcess(0x0001, False, pid)
    if not handle:
        raise OSError(ctypes.get_last_error(), "Cannot open Worker process")
    try:
        if not kernel32.TerminateProcess(handle, 0):
            raise OSError(ctypes.get_last_error(), "Cannot stop Worker process")
    finally:
        kernel32.CloseHandle(handle)
