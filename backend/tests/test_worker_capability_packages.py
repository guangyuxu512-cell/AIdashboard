import base64
import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from app.modules.workers.auth import get_worker_principal
from app.modules.workers.capability_package_api import build_capability_package_router
from app.modules.workers.service import WorkerPrincipal


def make_client(directory: Path | None) -> TestClient:
    app = FastAPI()
    app.include_router(build_capability_package_router(directory))

    def simulated_worker_auth(authorization: str | None = Header(default=None)) -> WorkerPrincipal:
        if authorization != "Bearer test-device":
            raise HTTPException(status_code=401)
        return WorkerPrincipal(device_id=uuid4())

    app.dependency_overrides[get_worker_principal] = simulated_worker_auth
    return TestClient(app)


def test_signed_release_is_only_available_to_authenticated_worker(tmp_path):
    manifest = b'{"schema_version":1,"sequence":1,"packages":[]}'
    signature = b"s" * 64
    data = b"synthetic archive bytes"
    digest = hashlib.sha256(data).hexdigest()
    (tmp_path / "manifest.json").write_bytes(manifest)
    (tmp_path / "manifest.sig").write_bytes(signature)
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages" / f"{digest}.zip").write_bytes(data)
    client = make_client(tmp_path)
    path = "/api/v1/worker/capability-packages"
    assert client.get(f"{path}/manifest").status_code == 401
    assert client.get(f"{path}/blobs/{digest}").status_code == 401
    headers = {"Authorization": "Bearer test-device"}
    response = client.get(f"{path}/manifest", headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert base64.b64decode(response.json()["manifest"]) == manifest
    assert base64.b64decode(response.json()["signature"]) == signature
    blob = client.get(f"{path}/blobs/{digest}", headers=headers)
    assert blob.status_code == 200 and blob.content == data
    assert blob.headers["content-type"] == "application/zip"
    assert client.get(f"{path}/blobs/not-a-digest", headers=headers).status_code == 404


def test_unconfigured_and_invalid_release_fail_closed(tmp_path):
    headers = {"Authorization": "Bearer test-device"}
    assert make_client(None).get("/api/v1/worker/capability-packages/manifest", headers=headers).status_code == 503
    (tmp_path / "manifest.json").write_bytes(b"{}")
    (tmp_path / "manifest.sig").write_bytes(b"short")
    assert make_client(tmp_path).get("/api/v1/worker/capability-packages/manifest", headers=headers).status_code == 404
