"""Read-only probes; connection failures are never interpreted as process failure."""

from __future__ import annotations

import os
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import psutil

from siyu_guard.storage import read_json


def _norm(path: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def sourcing_bootstrap(executable: str) -> str:
    """Prefer the stable launcher when a selected executable is an update."""
    path = Path(_norm(executable))
    for parent in path.parents:
        if parent.name.lower() == ".1688-updates":
            bootstrap = parent.parent / path.name
            return str(bootstrap) if bootstrap.is_file() else str(path)
    return str(path)


def process_presence(executable: str) -> str:
    """Return running, absent or unknown; access denied is not proof of absence."""
    expected = _norm(executable)
    name = os.path.basename(expected).lower()
    unknown = False
    for process in psutil.process_iter(["pid", "name"]):
        try:
            if (process.info.get("name") or "").lower() != name:
                continue
            if _norm(process.exe()) == expected:
                return "running"
            # Same executable name at another installation could be an update
            # or another instance. Do not launch a competing copy.
            unknown = True
        except psutil.NoSuchProcess:
            continue
        except (psutil.AccessDenied, OSError, psutil.ZombieProcess):
            unknown = True
    return "unknown" if unknown else "absent"


def worker_presence(executable: str, root: Path) -> str:
    """Follow the Worker's own PID/path/creation identity, including updated cores."""
    state = read_json(root / "worker-state.json", None)
    if isinstance(state, dict):
        try:
            process = psutil.Process(int(state["pid"]))
            path = _norm(str(state["executable_path"]))
            started = datetime.fromisoformat(state["started_at_utc"]).timestamp()
            if _norm(process.exe()) == path and abs(process.create_time() - started) < 2:
                return "running"
            # PID reused: do not trust the state. Check the configured launcher.
        except psutil.NoSuchProcess:
            pass
        except (psutil.AccessDenied, OSError, KeyError, TypeError, ValueError):
            return "unknown"
    # During the signed update handoff the state file may be absent. Never race
    # a running core/helper under the Worker's verified-release directory.
    releases = _norm(str(root / "runtime" / "base-releases")) + os.sep
    configured = _norm(executable)
    for process in psutil.process_iter(["pid", "name"]):
        name = (process.info.get("name") or "").lower()
        if name != os.path.basename(executable).lower():
            continue
        try:
            path = _norm(process.exe())
            if (path == configured or path.startswith(releases)) and any(
                    arg in ("--worker-core", "--worker-update-helper") for arg in process.cmdline()[1:]):
                return "running"
        except psutil.NoSuchProcess:
            continue
        except (psutil.AccessDenied, OSError, psutil.ZombieProcess):
            return "unknown"
    return "absent"


def sourcing_presence(executable: str, root: Path) -> tuple[str, str, bool]:
    """Identify the 1688 app using its task checkpoint and real process identity."""
    state = read_json(root / "watchdog-activity.json", None)
    if not isinstance(state, dict):
        return "unknown", "任务状态未确认", False
    pid, started, actual, count, uncertain = (state.get(k) for k in
        ("processId", "processStartedAt", "executablePath", "activeCount", "uncertain"))
    if (type(state.get("version")) is not int or state["version"] != 1 or type(pid) is not int or pid <= 0
            or type(started) not in (int, float) or not math.isfinite(started) or started <= 0 or not isinstance(actual, str)
            or type(count) is not int or count < 0 or type(uncertain) is not bool):
        return "unknown", "任务状态未确认", False
    configured, actual = _norm(sourcing_bootstrap(executable)), _norm(actual)
    selected = Path(_norm(executable))
    update_root = next((p for p in selected.parents if p.name.lower() == ".1688-updates"),
                       Path(configured).parent / ".1688-updates")
    updates = _norm(str(update_root / "releases")) + os.sep
    if actual != configured and not (actual.startswith(updates) and os.path.basename(actual) == os.path.basename(configured)):
        return "unknown", "程序路径未确认", False
    try:
        process = psutil.Process(pid)
        if _norm(process.exe()) == actual and abs(process.create_time() - started) < 3:
            return "running", ("工作中" if count else "结果待核查" if uncertain else "运行中"), False
    except psutil.NoSuchProcess:
        pass
    except (psutil.AccessDenied, OSError, ValueError):
        return "unknown", "进程状态未确认", False
    remaining = process_presence(executable)
    if remaining != "absent":
        return "unknown", "进程状态未确认", False
    return "absent", ("任务状态待核查" if count or uncertain else "已退出"), count == 0 and not uncertain


def worker_snapshot(root: Path, now: datetime | None = None) -> tuple[str, bool]:
    """Return a display state and whether a stopped Worker is provably idle.

    An idle-looking running snapshot is insufficient: a claim may have happened
    before its activity snapshot was persisted.
    """
    snapshot = read_json(root / "runtime-status.json", None)
    if not isinstance(snapshot, dict):
        return "本机状态未确认", False
    active = snapshot.get("active_task_count")
    if type(active) is not int or active < 0 or "current_task_id" not in snapshot:
        return "本机状态未确认", False
    current = snapshot["current_task_id"]
    if current is not None and (not isinstance(current, str) or not current):
        return "本机状态未确认", False
    if active or current:
        return "执行中", False
    checkpoint = (type(snapshot.get("watchdog_checkpoint_version")) is int and
                  snapshot["watchdog_checkpoint_version"] == 1)
    if "watchdog_checkpoint_version" in snapshot and not checkpoint:
        return "本机状态未确认", False
    uncertain = snapshot.get("watchdog_uncertain") is not False if checkpoint else False
    if snapshot.get("worker_status") == "stopped":
        return ("任务状态待核查", False) if uncertain else ("已安全停止", True)
    if snapshot.get("worker_status") != "running":
        return "本机状态未确认", False
    # New Workers persist busy before execution and retain uncertainty if a
    # terminal result was not durably saved. Match their checkpoint to their
    # own process record; old versions retain the conservative behavior.
    state = read_json(root / "worker-state.json", None)
    safely_idle = (snapshot.get("worker_status") == "running" and checkpoint and not uncertain
                   and isinstance(state, dict) and type(snapshot.get("watchdog_process_id")) is int
                   and snapshot["watchdog_process_id"] > 0 and type(state.get("pid")) is int
                   and snapshot["watchdog_process_id"] == state.get("pid"))
    if checkpoint and (not isinstance(state, dict) or type(snapshot.get("watchdog_process_id")) is not int
                       or type(state.get("pid")) is not int or snapshot["watchdog_process_id"] != state["pid"]):
        return "本机状态未确认", False
    if uncertain:
        return "结果待核查", False
    try:
        updated = datetime.fromisoformat(snapshot["updated_at"])
        age = ((now or datetime.now(timezone.utc)) - updated).total_seconds()
        if not 0 <= age <= 120:
            return "本机状态未确认", safely_idle
    except (KeyError, TypeError, ValueError):
        return "本机状态未确认", safely_idle
    if snapshot.get("connection_status") != "connected":
        return "连接异常", safely_idle
    return "在线", safely_idle


def bit_api(base_url: str = "http://127.0.0.1:54345") -> str:
    # The Bit API is local; do not send credentials or follow redirects.
    parsed = urlsplit(base_url)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost"):
        return "接口未确认"
    try:
        with httpx.Client(timeout=3, trust_env=False, follow_redirects=False) as client:
            response = client.post(base_url.rstrip("/") + "/browser/ports", json={})
        return "接口正常" if response.status_code == 200 and response.json().get("success") is True else "接口未确认"
    except (httpx.HTTPError, OSError, ValueError, AttributeError):
        return "接口未确认"


def collector_windows(base_url: str, token: str) -> tuple[list | None, str]:
    """Fetch existing collector heartbeats without following redirects."""
    parsed = urlsplit(base_url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or not token or any(c in token for c in "\r\n\x00")):
        return None, "配置错误"
    try:
        with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
            response = client.get(base_url.rstrip("/") + "/api/v1/collection/windows",
                                  headers={"Authorization": "Bearer " + token})
        if response.status_code in (401, 403):
            return None, "权限异常"
        if response.status_code != 200:
            return None, "连接异常"
        payload = response.json()
        rows = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return None, "状态未确认"
        return rows, ""
    except (httpx.HTTPError, OSError, ValueError, AttributeError):
        return None, "连接异常"


def collector_status(base_url: str, token: str, browser_id: str) -> str:
    """Reuse the existing Operations collector heartbeat; no browser is controlled."""
    rows, error = collector_windows(base_url, token)
    if rows is None:
        return error
    matches = [row for row in rows if isinstance(row, dict) and row.get("browserId") == browser_id]
    if not matches:
        return "未发现"
    if len(matches) != 1:
        return "标识重复"
    row = matches[0]
    if row.get("online") is False:
        return "心跳中断"
    if row.get("online") is not True:
        return "状态未确认"
    return {"busy": "工作中", "ready": "在线", "paused": "已暂停", "setup": "待配置"}.get(row.get("state"), "在线")
