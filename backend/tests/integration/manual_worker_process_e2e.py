"""Run the destructive Worker process E2E against control_center_dev.

This is intentionally an explicit manual script rather than a regular pytest test. It
starts real Backend and Worker processes, kills Worker-A during system.sleep, and
cleans only the two Device IDs created by this run.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.database import get_database_engine
from app.modules.devices.models import Device
from app.modules.tasks.models import Task
from app.modules.workers.models import DeviceRuntime, WorkerDeviceCredential
from app.modules.workers.service import WorkerService


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
WORKER_ROOT = PROJECT_ROOT / "worker"
BACKEND_PYTHON = BACKEND_ROOT / ".venv" / "Scripts" / "python.exe"
WORKER_PYTHON = WORKER_ROOT / ".venv" / "Scripts" / "python.exe"
API_BASE = "http://127.0.0.1:8000"


def wait_for(
    description: str,
    predicate: Callable[[], Any | None],
    timeout_seconds: int,
) -> Any:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            value = predicate()
            if value is not None:
                return value
        except (httpx.HTTPError, ConnectionError):
            pass
        time.sleep(1)
    raise TimeoutError(f"Timed out waiting for {description}")


def wait_task(client: httpx.Client, task_id: str, expected: str, timeout: int) -> Any:
    def check() -> Any | None:
        payload = client.get(f"/api/v1/tasks/{task_id}").raise_for_status().json()
        return payload if payload["status"] == expected else None

    return wait_for(f"Task {task_id}={expected}", check, timeout)


def wait_worker(
    client: httpx.Client,
    device_id: UUID,
    expected: str,
    timeout: int,
) -> Any:
    def check() -> Any | None:
        payload = client.get(f"/api/v1/devices/{device_id}").raise_for_status().json()
        runtime = payload["worker_runtime"]
        return payload if runtime and runtime["connection_status"] == expected else None

    return wait_for(f"Worker {device_id}={expected}", check, timeout)


def create_task(
    client: httpx.Client,
    device_id: UUID,
    skill_id: str,
    input_value: dict[str, Any],
) -> Any:
    return (
        client.post(
            "/api/v1/tasks",
            json={
                "target_device_id": str(device_id),
                "skill_id": skill_id,
                "input": input_value,
            },
        )
        .raise_for_status()
        .json()
    )


def start_worker(device_id: UUID, token: str, runtime_root: Path) -> subprocess.Popen:
    environment = os.environ.copy()
    environment.update(
        {
            "WORKER_SERVER_URL": API_BASE,
            "WORKER_DEVICE_ID": str(device_id),
            "WORKER_DEVICE_TOKEN": token,
            "WORKER_RUNTIME_ROOT": str(runtime_root),
        },
    )
    return subprocess.Popen(
        [str(WORKER_PYTHON), "-m", "app"],
        cwd=WORKER_ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def cleanup(device_ids: set[UUID]) -> None:
    if not device_ids:
        return
    with Session(get_database_engine()) as session:
        session.execute(delete(Task).where(Task.target_device_id.in_(device_ids)))
        session.execute(
            delete(DeviceRuntime).where(DeviceRuntime.device_id.in_(device_ids)),
        )
        session.execute(
            delete(WorkerDeviceCredential).where(
                WorkerDeviceCredential.device_id.in_(device_ids),
            ),
        )
        session.execute(delete(Device).where(Device.device_id.in_(device_ids)))
        session.commit()


def main() -> int:
    backend: subprocess.Popen | None = None
    worker_a: subprocess.Popen | None = None
    worker_b: subprocess.Popen | None = None
    device_ids: set[UUID] = set()

    with tempfile.TemporaryDirectory(prefix="worker-lite-e2e-") as runtime_value:
        runtime_root = Path(runtime_value)
        try:
            backend = subprocess.Popen(
                [
                    str(BACKEND_PYTHON),
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                ],
                cwd=BACKEND_ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            with httpx.Client(base_url=API_BASE, timeout=5) as client:
                wait_for(
                    "Backend health",
                    lambda: client.get("/health").raise_for_status().json(),
                    20,
                )
                print("E2E backend healthy")

                for name in ("3B-Lite-E2E-PC-A", "3B-Lite-E2E-PC-B"):
                    payload = (
                        client.post("/api/v1/devices", json={"display_name": name})
                        .raise_for_status()
                        .json()
                    )
                    device_ids.add(UUID(payload["device_id"]))
                device_a, device_b = tuple(device_ids)

                with Session(get_database_engine()) as session:
                    worker_service = WorkerService(session)
                    token_a = worker_service.issue_token(device_a)
                    token_b = worker_service.issue_token(device_b)
                print("E2E per-device tokens issued without plaintext output")

                worker_b = start_worker(device_b, token_b, runtime_root / "b")
                wait_worker(client, device_b, "online", 20)
                echo = create_task(
                    client,
                    device_a,
                    "system.echo",
                    {"message": "hello"},
                )
                time.sleep(5)
                pending = client.get(f"/api/v1/tasks/{echo['task_id']}").json()
                assert pending["status"] == "pending", "Worker-B claimed Worker-A task"
                print("E2E device isolation verified")

                worker_a = start_worker(device_a, token_a, runtime_root / "a-first")
                echo_result = wait_task(client, echo["task_id"], "success", 25)
                assert echo_result["result"] == {"message": "hello"}
                wait_worker(client, device_a, "online", 20)
                print("E2E echo PENDING-RUNNING-SUCCESS verified")

                yingdao = create_task(client, device_a, "yingdao.test", {})
                yingdao_result = wait_task(
                    client,
                    yingdao["task_id"],
                    "failed",
                    25,
                )
                assert yingdao_result["error_code"] == "RPA_PROVIDER_UNAVAILABLE"
                print("E2E unavailable Yingdao ended FAILED without RUNNING residue")

                sleep = create_task(
                    client,
                    device_a,
                    "system.sleep",
                    {"seconds": 45},
                )
                wait_task(client, sleep["task_id"], "running", 20)
                assert worker_a.poll() is None
                worker_a.kill()
                worker_a.wait(timeout=5)
                worker_a = None
                print("E2E Worker-A killed during system.sleep")

                wait_task(client, sleep["task_id"], "lost", 85)
                wait_worker(client, device_a, "offline", 10)
                print("E2E LOST and OFFLINE verified")

                worker_a = start_worker(device_a, token_a, runtime_root / "a-restart")
                wait_worker(client, device_a, "online", 20)
                restart = create_task(
                    client,
                    device_a,
                    "system.echo",
                    {"message": "restart-ok"},
                )
                restart_result = wait_task(client, restart["task_id"], "success", 25)
                assert restart_result["result"] == {"message": "restart-ok"}
                print("E2E same identity restart ONLINE and new task SUCCESS verified")
        finally:
            stop_process(worker_a)
            stop_process(worker_b)
            stop_process(backend)
            cleanup(device_ids)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
