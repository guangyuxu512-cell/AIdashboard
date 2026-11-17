"""Switch signed Worker versions after the current process has drained."""
from __future__ import annotations

import asyncio
import ctypes
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

from app.base_updates import BaseRelease, BaseUpdateError, BaseUpdater, verify_release
from app.local_config import write_json_atomic
from app.process_control import _current_process_identity, _inspect_windows_process
from app.shared.subprocesses import windows_no_window_creation_flags


_NONCE = re.compile(r"[0-9a-f]{32}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
TRIAL_ENV = "WORKER_BASE_UPDATE_TRIAL"


def _handoff(updater: BaseUpdater, nonce: str) -> tuple[Path, dict, BaseRelease]:
    if not _NONCE.fullmatch(nonce):
        raise BaseUpdateError("BASE_HANDOFF_INVALID")
    directory = updater.root / "handoffs" / nonce
    try:
        if any(path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())
               for path in (directory, directory.parent, updater.root)):
            raise ValueError
        path = directory / "handoff.json"
        if path.is_symlink() or path.stat().st_size > 4096:
            raise ValueError
        data = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or set(data) != {"nonce", "sequence", "version", "digest", "size", "parent_pid", "parent_started"}
                or data["nonce"] != nonce or type(data["parent_pid"]) is not int or data["parent_pid"] <= 0
                or type(data["sequence"]) is not int or data["sequence"] <= 0
                or type(data["size"]) is not int or data["size"] <= 0
                or not isinstance(data["digest"], str) or not _DIGEST.fullmatch(data["digest"])):
            raise ValueError
        datetime.fromisoformat(data["parent_started"])
        release = BaseRelease(data["sequence"], data["version"], data["digest"], data["size"],
                              updater.root / "releases" / f'{data["digest"][:16]}-{data["sequence"]}')
        verify_release(release, updater.public_key)
        return directory, data, release
    except (OSError, ValueError, TypeError, KeyError, BaseUpdateError):
        raise BaseUpdateError("BASE_HANDOFF_INVALID") from None


def start_handoff(updater: BaseUpdater, release: BaseRelease) -> bool:
    """Start the helper; the caller exits normally only after it is ready."""
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return False
    verify_release(release, updater.public_key)
    command = [str(release.executable), "--check-version", release.version]
    check = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=30, creationflags=windows_no_window_creation_flags(), check=False)
    if check.returncode:
        updater.reject(release)
        return False
    _, started = _current_process_identity()
    nonce = uuid.uuid4().hex
    directory = updater.root / "handoffs" / nonce
    directory.mkdir(parents=True, exist_ok=False)
    write_json_atomic(directory / "handoff.json", {"nonce": nonce, "sequence": release.sequence,
        "version": release.version, "digest": release.digest, "size": release.size,
        "parent_pid": os.getpid(), "parent_started": started.isoformat()})
    helper = subprocess.Popen([sys.executable, "--worker-update-helper", nonce],
        cwd=str(Path(sys.executable).resolve().parent), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, creationflags=windows_no_window_creation_flags(), close_fds=True)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if (directory / "helper.ready").is_file():
            return True
        if helper.poll() is not None:
            break
        time.sleep(0.1)
    (directory / "cancel").touch()
    return False


def _open_parent(pid: int, started: datetime) -> tuple[Path, int] | None:
    """Open the exact Worker process before signalling readiness; never kill it."""
    if os.name != "nt":
        return None
    handle = None
    try:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if not handle:
            return None
        path, actual_started = _inspect_windows_process(pid)
        if abs((actual_started - started).total_seconds()) >= 2:
            kernel.CloseHandle(handle)
            return None
        return path, int(handle)
    except (OSError, ValueError, TypeError):
        if handle:
            kernel.CloseHandle(handle)
        return None


def _wait_until_exit(handle: int, timeout_ms: int) -> bool:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel.WaitForSingleObject.restype = ctypes.c_uint32
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    try:
        return kernel.WaitForSingleObject(ctypes.c_void_p(handle), timeout_ms) == 0
    finally:
        kernel.CloseHandle(ctypes.c_void_p(handle))


def _launch_core(executable: Path, *, trial: str | None = None, disable_update: bool = False):
    env = os.environ.copy()
    env.pop(TRIAL_ENV, None)
    if trial:
        env[TRIAL_ENV] = trial
    if disable_update:
        env["WORKER_BASE_AUTO_UPDATE_ENABLED"] = "false"
    return subprocess.Popen([str(executable), "--worker-core"], cwd=str(executable.parent), env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=windows_no_window_creation_flags(), close_fds=True)


def apply_handoff(updater: BaseUpdater, nonce: str) -> bool:
    """A separate process waits for old Worker exit, then tries or rolls back."""
    directory, data, release = _handoff(updater, nonce)
    parent = _open_parent(data["parent_pid"], datetime.fromisoformat(data["parent_started"]))
    if parent is None:
        return False
    original, handle = parent
    (directory / "helper.ready").touch()
    if not _wait_until_exit(handle, 120_000):
        return False
    if (directory / "cancel").exists():
        _launch_core(original, disable_update=True)
        return False
    previous = None
    trial = None
    accepted = False
    try:
        previous = updater.state()
        trial = _launch_core(release.executable, trial=nonce)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if trial.poll() is not None:
                break
            try:
                ready = json.loads((directory / "trial.ready").read_text(encoding="utf-8"))
                if ready == {"nonce": nonce, "pid": trial.pid, "version": release.version}:
                    updater.accept(release)
                    if trial.poll() is not None:
                        break
                    (directory / "accepted").touch()
                    accepted = True
                    return True
            except (OSError, ValueError, TypeError):
                pass
            time.sleep(0.2)
        return False
    finally:
        if not accepted:
            if trial is not None and trial.poll() is None:
                trial.terminate()
                try:
                    trial.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    trial.kill()
                    trial.wait(timeout=5)
            try:
                if previous is None:
                    raise BaseUpdateError("BASE_STATE_INVALID")
                updater.save_state(previous)
                updater.reject(release)
                disable = False
            except (OSError, BaseUpdateError):
                disable = True
            _launch_core(original, disable_update=disable)


async def confirm_trial(updater: BaseUpdater, worker, nonce: str) -> bool:
    """A trial cannot claim tasks until the helper accepts its authenticated heartbeat."""
    directory, _, release = _handoff(updater, nonce)
    if not getattr(sys, "frozen", False) or Path(sys.executable).resolve() != release.executable.resolve():
        return False
    deadline = asyncio.get_running_loop().time() + 45
    while asyncio.get_running_loop().time() < deadline:
        if await worker._heartbeat_once(sync_skill_capabilities=False):
            write_json_atomic(directory / "trial.ready", {"nonce": nonce, "pid": os.getpid(), "version": release.version})
            break
        await asyncio.sleep(2)
    else:
        return False
    # Full integrity verification of a Windows package can take longer on a
    # busy machine; never let the trial claim work while it is still checked.
    deadline = asyncio.get_running_loop().time() + 120
    while asyncio.get_running_loop().time() < deadline:
        if (directory / "accepted").is_file():
            return True
        await asyncio.sleep(0.2)
    return False
