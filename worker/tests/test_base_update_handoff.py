import asyncio
import base64
from datetime import UTC, datetime
import hashlib
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.base_update_handoff import apply_handoff, confirm_trial
from app.base_updates import BaseUpdater
from app.local_config import write_json_atomic
from app.process_control import redirect_to_active_core
from app.worker import Worker


def staged(tmp_path):
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("ecommerce-worker.exe", b"synthetic")
        archive.writestr("VERSION", "0.5.9")
        archive.writestr("_internal/capability-public-key.txt", base64.b64encode(public))
    data = stream.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    raw = json.dumps({"schema_version": 1, "sequence": 1, "version": "0.5.9", "sha256": digest,
                      "size": len(data), "platform": "windows-x86_64"}).encode()

    class Source:
        async def fetch_base_release_manifest(self):
            return {"manifest": base64.b64encode(raw).decode(), "signature": base64.b64encode(key.sign(raw)).decode()}
        async def download_base_release(self, _digest, *, size, target):
            assert size == len(data)
            target.write_bytes(data)

    updater = BaseUpdater(tmp_path / "runtime" / "base-releases", public, "0.5.8")
    release = asyncio.run(updater.stage_when_idle(Source(), idle=True))
    nonce = uuid4().hex
    directory = updater.root / "handoffs" / nonce
    directory.mkdir(parents=True)
    write_json_atomic(directory / "handoff.json", {"nonce": nonce, "sequence": release.sequence,
        "version": release.version, "digest": release.digest, "size": release.size,
        "parent_pid": 123, "parent_started": datetime.now(UTC).isoformat()})
    return updater, release, nonce, directory


def test_successful_handoff_commits_verified_version_only_after_trial_heartbeat(tmp_path, monkeypatch):
    updater, release, nonce, directory = staged(tmp_path)
    old = tmp_path / "old-worker.exe"
    started = []
    trial = SimpleNamespace(pid=987, poll=lambda: None)
    monkeypatch.setattr("app.base_update_handoff._open_parent", lambda *_: (old, 123))
    monkeypatch.setattr("app.base_update_handoff._wait_until_exit", lambda *_: True)
    monkeypatch.setattr("app.base_update_handoff._launch_core", lambda executable, **kw: (started.append((executable, kw)) or trial))
    write_json_atomic(directory / "trial.ready", {"nonce": nonce, "pid": trial.pid, "version": release.version})
    assert apply_handoff(updater, nonce)
    assert started == [(release.executable, {"trial": nonce})]
    assert (directory / "accepted").exists() and updater.active_release() == release


def test_failed_trial_restores_previous_worker_and_blocks_repeated_bad_release(tmp_path, monkeypatch):
    updater, release, nonce, directory = staged(tmp_path)
    old = tmp_path / "old-worker.exe"
    calls = []
    trial = SimpleNamespace(pid=987, poll=lambda: 1)
    monkeypatch.setattr("app.base_update_handoff._open_parent", lambda *_: (old, 123))
    monkeypatch.setattr("app.base_update_handoff._wait_until_exit", lambda *_: True)
    monkeypatch.setattr("app.base_update_handoff._launch_core", lambda executable, **kw: (calls.append((executable, kw)) or trial))
    assert not apply_handoff(updater, nonce)
    assert calls == [(release.executable, {"trial": nonce}), (old, {"disable_update": False})]
    assert updater.state()["rejected_digest"] == release.digest and not (directory / "accepted").exists()


def test_trial_that_dies_during_final_validation_is_rolled_back(tmp_path, monkeypatch):
    updater, release, nonce, directory = staged(tmp_path)
    old = tmp_path / "old-worker.exe"
    calls = []
    trial = SimpleNamespace(pid=987, poll=lambda: None)
    monkeypatch.setattr("app.base_update_handoff._open_parent", lambda *_: (old, 123))
    monkeypatch.setattr("app.base_update_handoff._wait_until_exit", lambda *_: True)
    monkeypatch.setattr("app.base_update_handoff._launch_core", lambda executable, **kw: (calls.append((executable, kw)) or trial))
    original_accept = updater.accept
    def accept_then_exit(candidate):
        original_accept(candidate)
        trial.poll = lambda: 1
    monkeypatch.setattr(updater, "accept", accept_then_exit)
    write_json_atomic(directory / "trial.ready", {"nonce": nonce, "pid": trial.pid, "version": release.version})
    assert not apply_handoff(updater, nonce)
    assert calls == [(release.executable, {"trial": nonce}), (old, {"disable_update": False})]
    assert updater.state()["rejected_digest"] == release.digest and not (directory / "accepted").exists()


def test_helper_never_stops_or_replaces_a_parent_that_has_not_exited(tmp_path, monkeypatch):
    updater, _, nonce, _ = staged(tmp_path)
    monkeypatch.setattr("app.base_update_handoff._open_parent", lambda *_: (tmp_path / "old.exe", 123))
    monkeypatch.setattr("app.base_update_handoff._wait_until_exit", lambda *_: False)
    monkeypatch.setattr("app.base_update_handoff._launch_core", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()))
    assert not apply_handoff(updater, nonce)


def test_cancel_after_parent_exit_restarts_old_worker(tmp_path, monkeypatch):
    updater, _, nonce, directory = staged(tmp_path)
    old = tmp_path / "old.exe"
    calls = []
    monkeypatch.setattr("app.base_update_handoff._open_parent", lambda *_: (old, 123))
    monkeypatch.setattr("app.base_update_handoff._wait_until_exit", lambda *_: True)
    monkeypatch.setattr("app.base_update_handoff._launch_core", lambda executable, **kw: calls.append((executable, kw)))
    (directory / "cancel").touch()
    assert not apply_handoff(updater, nonce)
    assert calls == [(old, {"disable_update": True})]


def test_invalid_state_after_parent_exit_restarts_old_worker(tmp_path, monkeypatch):
    updater, _, nonce, _ = staged(tmp_path)
    old = tmp_path / "old.exe"
    calls = []
    monkeypatch.setattr("app.base_update_handoff._open_parent", lambda *_: (old, 123))
    monkeypatch.setattr("app.base_update_handoff._wait_until_exit", lambda *_: True)
    monkeypatch.setattr("app.base_update_handoff._launch_core", lambda executable, **kw: calls.append((executable, kw)))
    updater.save_state({"unexpected": "bad-state"})
    try:
        apply_handoff(updater, nonce)
    except Exception:
        pass
    assert calls == [(old, {"disable_update": True})]


def test_trial_waits_for_authenticated_heartbeat_and_acceptance_before_tasks(tmp_path, monkeypatch):
    updater, release, nonce, directory = staged(tmp_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(release.executable))
    calls = []
    async def heartbeat(*, sync_skill_capabilities):
        calls.append(sync_skill_capabilities)
        return True

    async def exercise():
        waiting = asyncio.create_task(confirm_trial(updater, SimpleNamespace(_heartbeat_once=heartbeat), nonce))
        await asyncio.sleep(0.05)
        assert (directory / "trial.ready").is_file() and not waiting.done()
        (directory / "accepted").touch()
        assert await waiting
    asyncio.run(exercise())
    assert calls == [False]


def test_worker_update_never_starts_while_task_or_unreported_event_is_active(tmp_path, monkeypatch):
    class Updater:
        calls = 0
        async def stage_when_idle(self, _client, *, idle):
            self.calls += 1
            assert idle
            return "staged"
    updater = Updater()
    settings = SimpleNamespace(runtime_root=tmp_path, base_update_interval_seconds=30)
    worker = Worker(settings, SimpleNamespace(), SimpleNamespace(), base_updater=updater)
    monkeypatch.setattr("app.base_update_handoff.start_handoff", lambda *_: True)
    worker._active_task_ids.add(uuid4())
    assert not asyncio.run(worker._update_base_if_idle()) and updater.calls == 0
    worker._active_task_ids.clear()
    worker.event_reporter = SimpleNamespace(buffer=["unreported"], flush_once=lambda: None)
    async def blocked_flush():
        return False
    worker.event_reporter.flush_once = blocked_flush
    assert not asyncio.run(worker._update_base_if_idle()) and updater.calls == 0
    worker.event_reporter = None
    worker._next_base_check = 0
    assert asyncio.run(worker._update_base_if_idle()) and updater.calls == 1


def test_old_shortcut_follows_verified_active_release_but_trial_and_fallback_do_not(tmp_path, monkeypatch):
    old = tmp_path / "old.exe"
    new = tmp_path / "new.exe"
    calls = []
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(old))
    monkeypatch.setattr("app.process_control.build_worker_core_command", lambda: [str(new), "--worker-core"])
    monkeypatch.setattr("app.process_control.subprocess.Popen", lambda command, **kwargs: calls.append(command))
    monkeypatch.delenv("WORKER_BASE_UPDATE_TRIAL", raising=False)
    monkeypatch.delenv("WORKER_BASE_AUTO_UPDATE_ENABLED", raising=False)
    assert redirect_to_active_core()
    assert calls == [[str(new), "--worker-core"]]
    monkeypatch.setenv("WORKER_BASE_UPDATE_TRIAL", "trial")
    assert not redirect_to_active_core()
    monkeypatch.delenv("WORKER_BASE_UPDATE_TRIAL")
    monkeypatch.setenv("WORKER_BASE_AUTO_UPDATE_ENABLED", "false")
    assert not redirect_to_active_core()
    assert len(calls) == 1
    monkeypatch.delenv("WORKER_BASE_AUTO_UPDATE_ENABLED")
    def launch_failure(*args, **kwargs):
        raise OSError("failed to start")
    monkeypatch.setattr("app.process_control.subprocess.Popen", launch_failure)
    assert not redirect_to_active_core()


def test_busy_prechecks_drain_before_update_and_no_new_claims(tmp_path, monkeypatch):
    from datetime import timedelta
    from app.contracts import WorkerTask
    stop = asyncio.Event()
    finished = []
    task = WorkerTask(task_id=uuid4(), skill_id="douyin.category_schema", input={},
                      lease_until=datetime.now(UTC) + timedelta(minutes=1))

    class Client:
        claimed = False
        async def claim(self):
            if not self.claimed:
                self.claimed = True
                return task
            return None
        async def claim_precheck(self):
            raise AssertionError("new work was claimed during drain")
        async def close(self):
            pass

    class Updater:
        async def update_available(self, _client):
            return True

    async def exercise():
        settings = SimpleNamespace(runtime_root=tmp_path, base_update_interval_seconds=30,
                                   poll_interval_seconds=0.02)
        worker = Worker(settings, Client(), SimpleNamespace(can_claim=lambda: True), base_updater=Updater())
        async def background(_stop):
            await _stop.wait()
        async def deliver():
            return True
        async def refresh():
            pass
        async def execute(_task):
            await asyncio.sleep(0.06)
            finished.append("task")
            worker._active_task_ids.discard(_task.task_id)
        async def update():
            if not finished:
                return False
            assert finished == ["task"]
            finished.append("update")
            return True
        monkeypatch.setattr(worker, "_heartbeat_supervisor", background)
        monkeypatch.setattr(worker, "_deliver_pending_terminals", deliver)
        monkeypatch.setattr(worker, "_refresh_capabilities_if_due", refresh)
        monkeypatch.setattr(worker, "_execute_claimed_task", execute)
        monkeypatch.setattr(worker, "_update_base_if_idle", update)
        await asyncio.wait_for(worker.run(stop), timeout=2)
    asyncio.run(exercise())
    assert finished == ["task", "update"]


def test_update_check_network_failure_does_not_pause_business_work(tmp_path):
    class OfflineUpdater:
        async def update_available(self, _client):
            raise OSError("offline")
    settings = SimpleNamespace(runtime_root=tmp_path, base_update_interval_seconds=30)
    worker = Worker(settings, SimpleNamespace(), SimpleNamespace(), base_updater=OfflineUpdater())
    asyncio.run(worker._check_base_update_for_drain())
    assert not worker._base_update_pending
