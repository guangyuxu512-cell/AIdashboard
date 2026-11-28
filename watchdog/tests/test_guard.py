import json
import base64
import hashlib
import os
import subprocess
import sys
import sysconfig
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import psutil
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from siyu_guard import guard, probes
from siyu_guard.storage import load_config, write_json


def snapshot(path, **changes):
    state = {"worker_status": "running", "active_task_count": 0, "current_task_id": None,
             "connection_status": "connected", "updated_at": datetime.now(timezone.utc).isoformat()}
    state.update(changes)
    write_json(path / "runtime-status.json", state)


@pytest.mark.parametrize("data,expected", [
    ({}, ("在线", False)),
    ({"connection_status": "disconnected"}, ("连接异常", False)),
    ({"active_task_count": 3, "connection_status": "disconnected"}, ("执行中", False)),
    ({"worker_status": "stopped"}, ("已安全停止", True)),
    ({"worker_status": "stopped", "active_task_count": 1}, ("执行中", False)),
    ({"worker_status": "stopped", "current_task_id": "still-active"}, ("执行中", False)),
    ({"active_task_count": None}, ("本机状态未确认", False)),
    ({"active_task_count": "0"}, ("本机状态未确认", False)),
    ({"current_task_id": ""}, ("本机状态未确认", False)),
    ({"worker_status": "stopped", "watchdog_checkpoint_version": "1"}, ("本机状态未确认", False)),
    ({"updated_at": (datetime.now(timezone.utc) - timedelta(minutes=4)).isoformat()}, ("本机状态未确认", False)),
])
def test_worker_snapshot_classification(tmp_path, data, expected):
    snapshot(tmp_path, **data)
    assert probes.worker_snapshot(tmp_path) == expected


def test_missing_and_corrupt_snapshot_are_not_idle(tmp_path):
    assert probes.worker_snapshot(tmp_path) == ("本机状态未确认", False)
    (tmp_path / "runtime-status.json").write_text("{", encoding="utf8")
    assert probes.worker_snapshot(tmp_path) == ("本机状态未确认", False)


def test_new_worker_idle_checkpoint_is_bound_to_process_identity(tmp_path):
    snapshot(tmp_path, watchdog_checkpoint_version=1, watchdog_uncertain=False, watchdog_process_id=123)
    write_json(tmp_path / "worker-state.json", {"pid": 123})
    assert probes.worker_snapshot(tmp_path) == ("在线", True)
    write_json(tmp_path / "worker-state.json", {"pid": 456})
    assert probes.worker_snapshot(tmp_path) == ("本机状态未确认", False)
    snapshot(tmp_path, watchdog_checkpoint_version=1, watchdog_uncertain=True, watchdog_process_id=123)
    write_json(tmp_path / "worker-state.json", {"pid": 123})
    assert probes.worker_snapshot(tmp_path) == ("结果待核查", False)
    snapshot(tmp_path, worker_status="unknown", watchdog_checkpoint_version=1,
             watchdog_uncertain=False, watchdog_process_id=123)
    assert probes.worker_snapshot(tmp_path) == ("本机状态未确认", False)


def test_uncertain_stopped_worker_is_never_safe(tmp_path):
    snapshot(tmp_path, worker_status="stopped", watchdog_checkpoint_version=1, watchdog_uncertain=True)
    assert probes.worker_snapshot(tmp_path) == ("任务状态待核查", False)


def test_never_restart_worker_on_network_or_ambiguous_exit(tmp_path, monkeypatch):
    now = [0]
    calls = []
    w = guard.Guard(tmp_path, clock=lambda: now[0], launcher=lambda *a, **kw: calls.append((a, kw)))
    monkeypatch.setattr(guard, "worker_root", lambda item=None: tmp_path)
    item = {"id": "w", "kind": "worker", "path": "worker.exe", "restart": True}
    snapshot(tmp_path, connection_status="disconnected")
    monkeypatch.setattr(guard, "worker_presence", lambda *args: "running")
    assert w.check(item) == "连接异常"
    monkeypatch.setattr(guard, "worker_presence", lambda *args: "absent")
    for state in ({}, {"active_task_count": 1}, {"worker_status": "stopped", "active_task_count": 1}):
        snapshot(tmp_path, **state)
        for instant in (0, 60, 600):
            now[0] = instant
            assert "待核查" in w.check(item)
    assert calls == []


def test_worker_restarts_only_after_grace_if_gracefully_stopped(tmp_path, monkeypatch):
    now = [0]
    calls = []
    snapshot(tmp_path, worker_status="stopped")
    monkeypatch.setattr(guard, "worker_root", lambda item=None: tmp_path)
    monkeypatch.setattr(guard, "worker_presence", lambda *args: "absent")
    w = guard.Guard(tmp_path, clock=lambda: now[0], launcher=lambda *a, **kw: calls.append((a, kw)))
    item = {"id": "w", "kind": "worker", "path": "worker.exe", "restart": True}
    assert w.check(item) == "等待恢复"
    now[0] = 30
    assert w.check(item) == "启动中"
    assert calls == [(("worker.exe",), {"worker": True})]
    assert w.check(item) == "等待重试"


def test_new_worker_crash_restarts_only_with_matching_idle_checkpoint(tmp_path, monkeypatch):
    now, calls = [0], []
    snapshot(tmp_path, watchdog_checkpoint_version=1, watchdog_uncertain=False, watchdog_process_id=123)
    write_json(tmp_path / "worker-state.json", {"pid": 123})
    monkeypatch.setattr(guard, "worker_root", lambda item=None: tmp_path)
    monkeypatch.setattr(guard, "worker_presence", lambda *args: "absent")
    w = guard.Guard(tmp_path, clock=lambda: now[0], launcher=lambda *a, **kw: calls.append((a, kw)))
    item = {"id": "w", "kind": "worker", "path": "worker.exe", "restart": True}
    assert w.check(item) == "等待恢复"
    now[0] = 30
    assert w.check(item) == "启动中"
    assert len(calls) == 1


def test_process_exit_grace_backoff_and_recovery(tmp_path, monkeypatch):
    now, launched = [0], []
    monkeypatch.setattr(guard, "process_presence", lambda _: "absent")
    w = guard.Guard(tmp_path, clock=lambda: now[0], launcher=lambda *a, **kw: launched.append(a))
    item = {"id": "p", "kind": "process", "path": "app.exe", "restart": True}
    assert w.check(item) == "等待恢复"
    now[0] = 29
    assert w.check(item) == "等待恢复"
    now[0] = 30
    assert w.check(item) == "启动中"
    now[0] = 31
    assert w.check(item) == "等待重试"
    now[0] = 60
    assert w.check(item) == "启动中"
    assert len(launched) == 2
    monkeypatch.setattr(guard, "process_presence", lambda _: "running")
    assert w.check(item) == "运行中"
    assert not w.failures


def test_unknown_process_never_restarted(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(guard, "process_presence", lambda _: "unknown")
    w = guard.Guard(tmp_path, clock=lambda: 500, launcher=lambda *a, **kw: calls.append(a))
    assert w.check({"id": "p", "kind": "process", "restart": True}) == "状态未确认"
    assert calls == []


def test_bit_network_failure_does_not_restart_browser(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(guard, "process_presence", lambda _: "running")
    monkeypatch.setattr(guard, "bit_api", lambda: "接口未确认")
    w = guard.Guard(tmp_path, launcher=lambda *a, **kw: calls.append(a))
    assert w.check({"id": "b", "kind": "bit", "path": "bit.exe", "restart": True}) == "运行中 · 接口未确认"
    assert calls == []


def test_service_transient_state_does_not_trigger_restart(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(guard, "service_presence", lambda _: "unknown")
    w = guard.Guard(tmp_path, service_launcher=lambda name: calls.append(name))
    assert w.check({"id": "s", "kind": "service", "service": "GameViewerService", "restart": True}) == "状态未确认"
    assert calls == []


def test_task_application_is_not_restarted_without_idle_proof(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(guard, "process_presence", lambda _: "absent")
    w = guard.Guard(tmp_path, clock=lambda: 1000, launcher=lambda *a, **kw: calls.append(a))
    item = {"id": "1688", "kind": "task_app", "path": "1688.exe", "restart": True}
    assert w.check(item) == "已退出 · 任务状态待核查"
    assert w.check(item) == "已退出 · 任务状态待核查"
    assert not calls


def signed_sourcing_fixture(tmp_path, monkeypatch):
    install = tmp_path / "installed"
    install.mkdir()
    executable = install / "1688-Sourcing-Preview.exe"
    executable.write_bytes(b"bootstrap")
    update_root = install / ".1688-updates"
    archive_bytes, exe_bytes, asar_bytes = b"archive", b"executable", b"asar"
    sha = lambda value: hashlib.sha256(value).hexdigest()
    digest = sha(archive_bytes)
    release = update_root / "releases" / f"4-0.1.11-{digest}"
    resources = release / "app" / "resources"
    resources.mkdir(parents=True)
    actual = resources.parent / executable.name
    actual.write_bytes(exe_bytes)
    (resources / "app.asar").write_bytes(asar_bytes)
    (release / "package.zip").write_bytes(archive_bytes)
    manifest = {"schema_version":1, "sequence":4, "version":"0.1.11", "sha256":digest,
                "size":len(archive_bytes), "platform":"windows-x86_64", "exe_sha256":sha(exe_bytes),
                "asar_sha256":sha(asar_bytes)}
    raw = json.dumps(manifest, separators=(",", ":"), sort_keys=True).encode()
    private = Ed25519PrivateKey.generate()
    der = private.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    monkeypatch.setattr(probes, "SOURCING_PUBLIC_KEY", base64.b64encode(der).decode())
    write_json(tmp_path / "data" / "update-state.json", {"schema":1, "root":str(update_root),
        "acceptedSequence":4, "active":{"manifest":base64.b64encode(raw).decode(),
                                      "signature":base64.b64encode(private.sign(raw)).decode()}})
    return str(executable), str(actual), release


def test_sourcing_checkpoint_distinguishes_idle_active_and_old_versions(tmp_path, monkeypatch):
    executable, actual, release = signed_sourcing_fixture(tmp_path, monkeypatch)
    marker = tmp_path / "watchdog-activity.json"
    assert probes.sourcing_presence(executable, tmp_path) == ("unknown", "任务状态未确认", False)
    state = {"version":1, "processId":12345, "processStartedAt":1700000000,
             "executablePath":actual, "activeCount":0, "uncertain":False}
    write_json(marker, state)
    monkeypatch.setattr(probes.psutil, "Process", lambda pid: (_ for _ in ()).throw(psutil.NoSuchProcess(pid)))
    monkeypatch.setattr(probes, "process_presence", lambda _: "absent")
    assert probes.sourcing_presence(executable, tmp_path) == ("absent", "已退出", True)
    state["activeCount"] = 1
    write_json(marker, state)
    assert probes.sourcing_presence(executable, tmp_path) == ("absent", "任务状态待核查", False)
    state.update(activeCount=0, uncertain=True)
    write_json(marker, state)
    assert probes.sourcing_presence(executable, tmp_path) == ("absent", "任务状态待核查", False)
    state.update(uncertain=False, executablePath=str(tmp_path / "unrelated" / "1688-Sourcing-Preview.exe"))
    write_json(marker, state)
    assert probes.sourcing_presence(executable, tmp_path) == ("unknown", "程序路径未确认", False)


def test_sourcing_rejects_stale_or_tampered_signed_release(tmp_path, monkeypatch):
    executable, actual, release = signed_sourcing_fixture(tmp_path, monkeypatch)
    marker = tmp_path / "watchdog-activity.json"
    write_json(marker, {"version":1, "processId":12345, "processStartedAt":1700000000,
                        "executablePath":actual, "activeCount":0, "uncertain":False})
    monkeypatch.setattr(probes.psutil, "Process", lambda pid: (_ for _ in ()).throw(psutil.NoSuchProcess(pid)))
    monkeypatch.setattr(probes, "process_presence", lambda _: "absent")
    assert probes.sourcing_presence(executable, tmp_path) == ("absent", "已退出", True)
    state_path = tmp_path / "data" / "update-state.json"
    state = json.loads(state_path.read_text(encoding="utf8"))
    state["acceptedSequence"] = 3  # updater rolled back to the previous version
    write_json(state_path, state)
    assert probes.sourcing_presence(executable, tmp_path) == ("absent", "版本待核查", False)
    state["acceptedSequence"] = 4
    write_json(state_path, state)
    original_signature = state["active"]["signature"]
    state["active"]["signature"] = base64.b64encode(bytes(64)).decode()
    write_json(state_path, state)
    assert probes.sourcing_presence(executable, tmp_path) == ("absent", "版本待核查", False)
    state["active"]["signature"] = original_signature
    write_json(state_path, state)
    (release / "app" / "resources" / "app.asar").write_bytes(b"tampered")
    assert probes.sourcing_presence(executable, tmp_path) == ("absent", "版本待核查", False)


def test_sourcing_checkpoint_recognizes_signed_update_process(tmp_path, monkeypatch):
    executable = str(tmp_path / "installed" / "1688-Sourcing-Preview.exe")
    updated = str(tmp_path / "installed" / ".1688-updates" / "releases" / "v1" / "1688-Sourcing-Preview.exe")
    write_json(tmp_path / "watchdog-activity.json", {"version":1, "processId":12345,
        "processStartedAt":1700000000, "executablePath":updated, "activeCount":1, "uncertain":False})
    class Process:
        def exe(self): return updated
        def create_time(self): return 1700000001
    monkeypatch.setattr(probes.psutil, "Process", lambda _: Process())
    assert probes.sourcing_presence(executable, tmp_path) == ("running", "工作中", False)


def test_sourcing_selection_uses_stable_launcher_if_user_picks_update(tmp_path):
    install = tmp_path / "installed"
    release = install / ".1688-updates" / "releases" / "v1"
    release.mkdir(parents=True)
    bootstrap = install / "1688-Sourcing-Preview.exe"
    selected = release / bootstrap.name
    bootstrap.write_bytes(b"fixture")
    selected.write_bytes(b"fixture")
    assert probes._norm(probes.sourcing_bootstrap(str(selected))) == probes._norm(str(bootstrap))


def test_sourcing_guard_only_restarts_after_proven_idle(tmp_path, monkeypatch):
    now, calls, idle = [0], [], [False]
    monkeypatch.setattr(guard, "sourcing_presence", lambda *args:
                        ("absent", "已退出" if idle[0] else "任务状态待核查", idle[0]))
    w = guard.Guard(tmp_path, clock=lambda: now[0], launcher=lambda *a, **kw: calls.append((a, kw)))
    item = {"id":"1688", "kind":"sourcing", "path":"1688.exe", "restart":True}
    assert w.check(item) == "已退出 · 任务状态待核查"
    idle[0] = True
    assert w.check(item) == "等待恢复"
    now[0] = 30
    assert w.check(item) == "启动中"
    assert calls == [(("1688.exe",), {"worker":False})]


def test_collector_offline_and_network_failures_never_touch_browser(tmp_path, monkeypatch):
    calls = []
    w = guard.Guard(tmp_path, unprotect=lambda _: "hidden", launcher=lambda *a, **kw: calls.append(a))
    item = {"id": "p", "kind": "plugin", "protected_token": "encrypted", "url": "https://example.invalid", "browser_id": "b"}
    for result in ("离线", "连接异常", "权限异常", "工作中"):
        monkeypatch.setattr(guard, "collector_status", lambda *args: result)
        assert w.check(item) == result
    assert not calls


def test_daemon_does_not_expose_tokens_in_status(tmp_path, monkeypatch):
    write_json(tmp_path / "config.json", {"items": [{"id": "p", "name": "插件", "kind": "plugin", "enabled": True,
                                                     "protected_token": "encrypted", "url": "https://example.invalid", "browser_id": "b"}]})
    monkeypatch.setattr(guard, "collector_status", lambda *args: "在线")
    result = guard.Guard(tmp_path, unprotect=lambda _: "secret-not-for-output").poll()
    text = (tmp_path / "status.json").read_text(encoding="utf8")
    assert result[0]["state"] == "在线"
    assert "secret-not-for-output" not in text and "encrypted" not in text


def test_duplicate_software_is_only_checked_once(tmp_path, monkeypatch):
    items = [{"id": "a", "name": "A", "kind": "process", "path": "C:/app.exe", "enabled": True},
             {"id": "b", "name": "B", "kind": "task_app", "path": "C:/app.exe", "enabled": True}]
    write_json(tmp_path / "config.json", {"items": items})
    calls = []
    monkeypatch.setattr(guard, "process_presence", lambda path: calls.append(path) or "running")
    result = guard.Guard(tmp_path).poll()
    assert [row["state"] for row in result] == ["重复配置", "重复配置"]
    assert calls == []


def test_instance_lock_prevents_double_daemon(tmp_path):
    with guard.InstanceLock(tmp_path) as first:
        assert first
        with guard.InstanceLock(tmp_path) as second:
            assert not second
    with guard.InstanceLock(tmp_path) as after_exit:
        assert after_exit


def test_atomic_config_replaces_file_and_reads_corruption_safely(tmp_path):
    path = tmp_path / "config.json"
    write_json(path, {"items": [{"id": "a"}]})
    assert load_config(tmp_path)["items"][0]["id"] == "a"
    path.write_text("{broken", encoding="utf8")
    assert load_config(tmp_path) == {"items": []}


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response, self.error = response, error
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def get(self, *args, **kwargs):
        if self.error: raise self.error
        return self.response
    def post(self, *args, **kwargs):
        if self.error: raise self.error
        return self.response


@pytest.mark.parametrize("response,expected", [
    (httpx.Response(200, json={"items": [{"browserId": "1", "online": True, "state": "busy"}]}), "工作中"),
    (httpx.Response(200, json={"items": [{"browserId": "1", "online": False, "state": "offline"}]}), "心跳中断"),
    (httpx.Response(200, json={"items": []}), "未发现"),
    (httpx.Response(200, json={}), "状态未确认"),
    (httpx.Response(403), "权限异常"),
    (httpx.Response(502), "连接异常"),
    (httpx.Response(302, headers={"Location": "https://other.invalid"}), "连接异常"),
])
def test_collector_health_contract(response, expected, monkeypatch):
    monkeypatch.setattr(probes.httpx, "Client", lambda **kw: FakeClient(response))
    assert probes.collector_status("https://example.invalid", "token", "1") == expected


def test_collector_transport_failure_and_insecure_url(monkeypatch):
    monkeypatch.setattr(probes.httpx, "Client", lambda **kw: FakeClient(error=httpx.ConnectError("offline")))
    assert probes.collector_status("https://example.invalid", "token", "1") == "连接异常"
    assert probes.collector_status("http://example.invalid", "token", "1") == "配置错误"


def test_collector_rejects_ambiguous_browser_identity(monkeypatch):
    response = httpx.Response(200, json={"items": [
        {"browserId": "1", "online": True, "state": "ready"},
        {"browserId": "1", "online": True, "state": "busy"}]})
    monkeypatch.setattr(probes.httpx, "Client", lambda **kw: FakeClient(response))
    assert probes.collector_status("https://example.invalid", "token", "1") == "标识重复"


def test_bit_http_contract_and_no_remote_api(monkeypatch):
    monkeypatch.setattr(probes.httpx, "Client", lambda **kw: FakeClient(httpx.Response(200, json={"success": True})))
    assert probes.bit_api() == "接口正常"
    assert probes.bit_api("http://example.invalid") == "接口未确认"


def test_real_process_identity_and_worker_pid_reuse(tmp_path):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, creationflags=guard.no_window())
    try:
        process = psutil.Process(child.pid)
        executable = process.exe()
        started = datetime.fromtimestamp(process.create_time(), timezone.utc)
        write_json(tmp_path / "worker-state.json", {"pid": child.pid, "executable_path": executable,
                   "started_at_utc": started.isoformat(), "device_id": "test"})
        assert probes.worker_presence(executable, tmp_path) == "running"
        # Same PID but different creation time must not be accepted as the Worker.
        write_json(tmp_path / "worker-state.json", {"pid": child.pid, "executable_path": executable,
                   "started_at_utc": (started - timedelta(seconds=30)).isoformat(), "device_id": "test"})
        assert probes.worker_presence(executable, tmp_path) != "running"
    finally:
        child.terminate()
        child.wait(timeout=10)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows processes and DPAPI")
def test_background_peers_restart_each_other_without_touching_user_processes(tmp_path):
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, SIYU_GUARD_DATA_ROOT=str(tmp_path),
               PYTHONPATH=os.pathsep.join((str(root / "watchdog"), str(root / "worker"),
                                           sysconfig.get_paths()["purelib"])))
    python = getattr(sys, "_base_executable", sys.executable)
    sentinel = subprocess.Popen([python, "-m", "siyu_guard", "--sentinel"],
                                cwd=str(root / "watchdog"), env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=guard.no_window())

    def wait_pid(filename, old=None, timeout=18):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                value = json.loads((tmp_path / filename).read_text(encoding="utf8"))["pid"]
                if value != old and psutil.pid_exists(value):
                    return value
            except (OSError, ValueError, KeyError):
                pass
            time.sleep(0.1)
        raise AssertionError("guard peer did not start")

    known = []
    try:
        first_sentinel = wait_pid("sentinel-status.json")
        assert first_sentinel == sentinel.pid
        first_daemon = wait_pid("status.json")
        assert psutil.Process(first_daemon).ppid() == first_sentinel
        known = [psutil.Process(first_sentinel), psutil.Process(first_daemon)]
        known[-1].terminate()
        second_daemon = wait_pid("status.json", old=first_daemon)
        assert psutil.Process(second_daemon).ppid() == first_sentinel
        known.append(psutil.Process(second_daemon))
        sentinel.terminate()
        second_sentinel = wait_pid("sentinel-status.json", old=first_sentinel)
        assert psutil.Process(second_sentinel).ppid() == second_daemon
        known.append(psutil.Process(second_sentinel))
    finally:
        # The test only stops peers whose PIDs it received from its isolated root.
        (tmp_path / "stopped").touch()
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline and any(process.is_running() for process in known):
            if sentinel.poll() is not None:
                sentinel.wait(timeout=1)
            time.sleep(.1)
        for process in known:
            try:
                if process.is_running() and any(arg in ("--daemon", "--sentinel") for arg in process.cmdline()):
                    process.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
