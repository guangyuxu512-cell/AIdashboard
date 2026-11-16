import asyncio
import base64
import hashlib
import io
import json
import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import httpx

from app.capability_host import CapabilityHost
from app.capability_runtime import CapabilityRuntime
from app.capability_updates import CapabilityUpdater
from app.contracts import WorkerTask


def test_new_signed_skill_is_loaded_advertised_and_executed(tmp_path):
    key = Ed25519PrivateKey.generate()
    public_key = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    updater = CapabilityUpdater(tmp_path / "capabilities", public_key, 1)
    output = io.BytesIO()
    source = '''from app.contracts import ExecutionResult, ExecutionStatus
SKILL_ID="new.example"
INPUT_SCHEMA={"type":"object","properties":{},"additionalProperties":False}
async def execute(host, task):
    return ExecutionResult(status=ExecutionStatus.SUCCESS, result={"ran": True})
'''
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("capability.py", source)
    blob = output.getvalue()
    digest = hashlib.sha256(blob).hexdigest()
    manifest = json.dumps({"schema_version": 1, "sequence": 1, "packages": [{"skill_id": "new.example",
        "version": "1.0", "entrypoint": "capability.py", "host_api_version": 1,
        "sha256": digest, "size": len(blob)}]}, separators=(",", ":")).encode()

    class Client:
        async def fetch_capability_manifest(self):
            return {"manifest": base64.b64encode(manifest).decode(), "signature": base64.b64encode(key.sign(manifest)).decode()}

        async def download_capability_package(self, value, *, max_size):
            assert value == digest
            return blob

    runtime = CapabilityRuntime(updater, SimpleNamespace(device_id=uuid4()))
    assert asyncio.run(updater.sync_when_idle(Client(), idle=True, validate_entry=runtime.validate_entry))
    runtime.refresh()
    assert [(item.skill_id, item.version) for item in runtime.descriptors()] == [("new.example", "1.0")]
    task = WorkerTask(task_id=uuid4(), skill_id="new.example", input={}, lease_until=datetime.now(UTC) + timedelta(seconds=60))
    assert asyncio.run(runtime.execute(task)).result == {"ran": True}


def test_sensitive_url_and_cookie_never_enter_httpx_logs(caplog):
    cookie = "testcookie=synthetic-cookie-secret"
    signed = {"url": "https://fxg.jinritemai.com/product/tproduct/getSchema?appid=1&msToken=synthetic-token-secret&a_bogus=synthetic-signature-secret",
              "body": json.dumps({"context": {"category_id": "123"}, "model": {"title": {"value": "demo"}}})}

    def platform(request):
        assert request.headers["cookie"] == cookie
        return httpx.Response(200, json={"code": 0})

    host = CapabilityHost(uuid4(), None, None, transport=httpx.MockTransport(platform))
    with caplog.at_level(logging.INFO, logger="httpx"):
        status, _ = asyncio.run(host.post_schema(signed, cookie, "synthetic-agent", {"category_id": "123", "title": "demo"}))
    assert status == 200
    assert "synthetic-cookie-secret" not in caplog.text
    assert "synthetic-token-secret" not in caplog.text
    assert "synthetic-signature-secret" not in caplog.text


def test_host_rejects_wrong_platform_target_without_request():
    calls = []
    host = CapabilityHost(uuid4(), None, None, transport=httpx.MockTransport(lambda request: calls.append(request)))
    signed = {"url": "https://untrusted.invalid/product/tproduct/getSchema?a_bogus=x", "body": "{}"}
    try:
        asyncio.run(host.post_schema(signed, "synthetic-cookie", "agent", {}))
    except RuntimeError as error:
        assert str(error) == "PRECHECK_TRANSPORT_FAILED"
    else:
        raise AssertionError("unexpected request")
    assert calls == []
