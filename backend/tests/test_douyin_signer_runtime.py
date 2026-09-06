from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from typing import Iterator

import httpx
from pydantic import SecretStr

from app.core.config import Settings
from app.integrations.douyin_signer import DouyinSignerClient, DouyinSignRequest


SIGNER_ROOT = Path(__file__).resolve().parents[1] / "douyin-signer"
SERVER_PATH = SIGNER_ROOT / "server.js"
TEST_API_KEY = "test-only-signer-key"


@dataclass
class RunningSigner:
    base_url: str
    process: subprocess.Popen[str]
    stdout: str = ""
    stderr: str = ""


def _available_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _runtime_environment(*, port: int, api_key: str | None) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("BACKEND_DOUYIN_SIGNER_API_KEY", None)
    environment["PORT"] = str(port)
    if api_key is not None:
        environment["BACKEND_DOUYIN_SIGNER_API_KEY"] = api_key
    return environment


@contextmanager
def running_signer() -> Iterator[RunningSigner]:
    node = shutil.which("node")
    assert node is not None, "Douyin Signer runtime requires Node.js"
    port = _available_loopback_port()
    process = subprocess.Popen(
        [node, str(SERVER_PATH)],
        cwd=SIGNER_ROOT,
        env=_runtime_environment(port=port, api_key=TEST_API_KEY),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    runtime = RunningSigner(
        base_url=f"http://127.0.0.1:{port}",
        process=process,
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            try:
                response = httpx.get(f"{runtime.base_url}/health", timeout=0.2)
            except httpx.RequestError:
                time.sleep(0.05)
                continue
            if response.status_code == 200:
                break
        else:
            raise AssertionError("Douyin Signer did not become healthy")
        assert process.poll() is None, "Douyin Signer exited before becoming healthy"
        yield runtime
    finally:
        if process.poll() is None:
            process.terminate()
        runtime.stdout, runtime.stderr = process.communicate(timeout=10)


def _sign_payload(*, host: str, ms_token: str | None = None) -> dict[str, str]:
    payload = {
        "host": host,
        "full_url": f"https://{host}/compass_api/test?item=1",
        "method": "GET",
        "user_agent": "Douyin Signer Foundation Test",
    }
    if ms_token is not None:
        payload["ms_token"] = ms_token
    return payload


def test_signer_refuses_to_start_without_api_key() -> None:
    node = shutil.which("node")
    assert node is not None, "Douyin Signer runtime requires Node.js"
    process = subprocess.run(
        [node, str(SERVER_PATH)],
        cwd=SIGNER_ROOT,
        env=_runtime_environment(port=_available_loopback_port(), api_key=None),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert process.returncode != 0
    assert "BACKEND_DOUYIN_SIGNER_API_KEY" in process.stderr


def test_signer_health_auth_isolation_and_backend_client() -> None:
    with running_signer() as runtime:
        health = httpx.get(f"{runtime.base_url}/health", timeout=5)
        assert health.status_code == 200
        assert health.json() == {"ok": True, "service": "abogus-signer"}

        rejected = httpx.post(
            f"{runtime.base_url}/sign",
            headers={"X-API-Key": "incorrect-test-key"},
            json=_sign_payload(host="first.example.invalid"),
            timeout=5,
        )
        assert rejected.status_code == 401

        first = httpx.post(
            f"{runtime.base_url}/sign",
            headers={"X-API-Key": TEST_API_KEY},
            json=_sign_payload(
                host="first.example.invalid",
                ms_token="synthetic-context-a",
            ),
            timeout=15,
        )
        assert first.status_code == 200
        assert first.json()["ok"] is True
        assert first.json()["a_bogus"]

        second = httpx.post(
            f"{runtime.base_url}/sign",
            headers={"X-API-Key": TEST_API_KEY},
            json=_sign_payload(host="second.example.invalid"),
            timeout=15,
        )
        assert second.status_code == 200
        assert second.json()["ok"] is True
        assert second.json()["a_bogus"]
        assert second.json()["msToken"] != "synthetic-context-a"
        assert "access-control-allow-origin" not in second.headers

        browser_route = httpx.post(
            f"{runtime.base_url}/browser/product-video-sign",
            headers={"X-API-Key": TEST_API_KEY},
            json={},
            timeout=5,
        )
        assert browser_route.status_code == 404

        backend_client = DouyinSignerClient(
            settings=Settings(
                _env_file=None,
                douyin_signer_url=runtime.base_url,
                douyin_signer_api_key=SecretStr(TEST_API_KEY),
            ),
        )
        result = backend_client.sign(
            DouyinSignRequest(
                host="backend.example.invalid",
                full_url=(
                    "https://backend.example.invalid/compass_api/test?item=2"
                ),
                method="GET",
                user_agent="Douyin Signer Backend Client Test",
            ),
        )
        assert result.a_bogus.get_secret_value()

    assert TEST_API_KEY not in runtime.stdout
    assert TEST_API_KEY not in runtime.stderr
    assert "synthetic-context-a" not in runtime.stdout
    assert "synthetic-context-a" not in runtime.stderr
