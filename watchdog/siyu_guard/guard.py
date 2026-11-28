"""Supervise selected applications without killing live processes or submitting work."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

from siyu_guard.probes import bit_api, collector_status, process_presence, sourcing_presence, worker_presence, worker_snapshot
from siyu_guard.storage import load_config, write_json


def worker_root(item: dict | None = None) -> Path:
    return Path((item or {}).get("data_root") or os.environ.get("ECOMMERCE_WORKER_DATA_ROOT") or
                Path(os.environ.get("LOCALAPPDATA", ".")) / "EcommerceAIWorker").resolve()


def no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def start_program(path: str, *, worker: bool = False) -> None:
    executable = Path(path)
    if not executable.is_absolute() or not executable.is_file() or executable.suffix.lower() != ".exe":
        raise OSError("程序文件不可用")
    subprocess.Popen([str(executable)] + (["--worker-core"] if worker else []),
                     cwd=str(executable.parent), stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     close_fds=True, creationflags=no_window())


def service_presence(name: str) -> str:
    if os.name != "nt":
        return "unknown"
    try:
        status = psutil.win_service_get(name).status()
    except (psutil.Error, OSError, ValueError):
        return "unknown"
    if status == "running":
        return "running"
    if status == "stopped":
        return "absent"
    return "unknown"  # start/stop pending must finish before another start


def start_service(name: str) -> None:
    result = subprocess.run(["sc.exe", "start", name], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=no_window(), timeout=15, check=False)
    if result.returncode:
        raise OSError("服务启动失败")


class Guard:
    def __init__(self, root: Path, *, clock=time.monotonic, launcher=start_program,
                 service_launcher=start_service, unprotect=None):
        self.root, self.clock = root, clock
        self.launcher, self.service_launcher = launcher, service_launcher
        self.unprotect = unprotect
        self.missing_since: dict[str, float] = {}
        self.next_attempt: dict[str, float] = {}
        self.failures: dict[str, int] = {}

    @staticmethod
    def _identity(item: dict) -> tuple:
        kind = item.get("kind")
        if kind in ("process", "task_app", "worker", "bit", "sourcing"):
            return ("path", os.path.normcase(os.path.realpath(os.path.abspath(str(item.get("path", ""))))))
        if kind == "service":
            return ("service", str(item.get("service", "")).lower())
        return (str(kind), str(item.get("url", "")), str(item.get("browser_id", "")))

    def poll(self) -> list[dict]:
        rows = []
        config = load_config(self.root)
        items = [item for item in config.get("items", []) if isinstance(item, dict)]
        identities = [self._identity(item) for item in items if item.get("enabled") is True]
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            row = {"id": item["id"], "name": str(item.get("name", "")), "state": "未启用"}
            if item.get("enabled") is True:
                try:
                    if identities.count(self._identity(item)) > 1:
                        row["state"] = "重复配置"
                    else:
                        row["state"] = self.check(item)
                except Exception:
                    # Do not leak paths, tokens, exception text, or response bodies.
                    row["state"] = "检查异常"
            rows.append(row)
        write_json(self.root / "status.json", {"pid": os.getpid(), "updated_at": time.time(), "items": rows})
        return rows

    def check(self, item: dict) -> str:
        kind = item.get("kind")
        if kind == "plugin":
            if not self.unprotect or not item.get("protected_token"):
                return "待配置"
            try:
                token = self.unprotect(item["protected_token"])
            except Exception:
                return "凭据不可用"
            return collector_status(item.get("url", ""), token, item.get("browser_id", ""))
        if kind == "service":
            presence = service_presence(str(item.get("service", "")))
        elif kind == "worker":
            presence = worker_presence(str(item.get("path", "")), worker_root(item))
        elif kind == "sourcing":
            roaming = Path(os.environ.get("APPDATA", "."))
            presence, detail, sourcing_idle = sourcing_presence(str(item.get("path", "")), roaming / "1688采集")
        elif kind in ("process", "bit", "task_app"):
            presence = process_presence(str(item.get("path", "")))
        else:
            return "配置错误"
        key = item["id"]
        if presence == "running":
            self.missing_since.pop(key, None)
            self.failures.pop(key, None)
            if kind == "worker":
                return worker_snapshot(worker_root(item))[0]
            if kind == "bit":
                return "运行中 · " + bit_api()
            if kind == "sourcing":
                return detail
            return "运行中"
        if presence != "absent":
            self.missing_since.pop(key, None)
            return detail if kind == "sourcing" else "状态未确认"
        if kind == "worker" and not worker_snapshot(worker_root(item))[1]:
            return "已退出 · 任务状态待核查"
        if kind == "sourcing" and not sourcing_idle:
            return "已退出 · " + detail
        if kind == "task_app":
            # For example, current 1688 bridge re-claims its existing lease on
            # startup. Without a durable idle proof a restart can repeat work.
            return "已退出 · 任务状态待核查"
        if item.get("restart") is not True:
            return "未运行"
        now = self.clock()
        since = self.missing_since.setdefault(key, now)
        # Wait for transient exits and signed Worker update handoffs.
        if now - since < 30:
            return "等待恢复"
        if now < self.next_attempt.get(key, 0):
            return "等待重试"
        try:
            if kind == "service":
                self.service_launcher(str(item.get("service", "")))
            else:
                self.launcher(str(item.get("path", "")), worker=kind == "worker")
            result = "启动中"
        except (OSError, subprocess.SubprocessError):
            result = "启动失败"
        count = min(self.failures.get(key, 0) + 1, 5)
        self.failures[key] = count
        self.next_attempt[key] = now + min(30 * 2 ** (count - 1), 300)
        return result


class InstanceLock:
    """Per-user daemon lock; the OS releases it if the process exits."""
    def __init__(self, root: Path, name: str = "daemon.lock"):
        self.root = root
        self.name = name
        self.file = None

    def __enter__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.file = (self.root / self.name).open("a+b")
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            self.file = None
            return False
        return True

    def __exit__(self, *args):
        if self.file is not None:
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            self.file.close()


def peer_command(role: str) -> list[str]:
    if role not in ("daemon", "sentinel"):
        raise ValueError("invalid role")
    if getattr(sys, "frozen", False):
        return [sys.executable, "--" + role]
    return [sys.executable, "-m", "siyu_guard", "--" + role]


def ensure_peer(root: Path, role: str) -> None:
    # The lock is the identity; never kill another process or trust a stale PID.
    with InstanceLock(root, role + ".lock") as free:
        if not free:
            return
    # Release before spawning so a fast child can take its own lock. If two
    # callers race here the child's instance lock still admits only one.
    subprocess.Popen(peer_command(role), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, close_fds=True,
                     cwd=str(Path(__file__).resolve().parents[1]), creationflags=no_window())


def daemon(root: Path) -> int:
    with InstanceLock(root) as acquired:
        if not acquired:
            return 0
        from app.local_config import WindowsDpapiTokenProtector
        guard = Guard(root, unprotect=WindowsDpapiTokenProtector().unprotect)
        while not (root / "stopped").exists():
            try:
                ensure_peer(root, "sentinel")
            except (OSError, subprocess.SubprocessError):
                pass
            try:
                guard.poll()
            except Exception:
                pass
            time.sleep(10)


def sentinel(root: Path) -> int:
    with InstanceLock(root, "sentinel.lock") as acquired:
        if not acquired:
            return 0
        while not (root / "stopped").exists():
            try:
                write_json(root / "sentinel-status.json", {"pid": os.getpid(), "updated_at": time.time()})
                ensure_peer(root, "daemon")
            except (OSError, subprocess.SubprocessError):
                pass
            time.sleep(10)
