import base64
import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from app.modules.workers.auth import get_worker_principal
from app.modules.workers.base_update_api import build_base_update_router
from app.modules.workers.service import WorkerPrincipal


def client(root: Path | None) -> TestClient:
    application = FastAPI()
    application.include_router(build_base_update_router(root))

    def auth(authorization: str | None = Header(default=None)) -> WorkerPrincipal:
        if authorization != "Bearer synthetic-device":
            raise HTTPException(status_code=401)
        return WorkerPrincipal(device_id=uuid4())

    application.dependency_overrides[get_worker_principal] = auth
    return TestClient(application)


def test_worker_release_is_authenticated_and_streamed_from_fixed_directory(tmp_path):
    root = tmp_path / "worker-base"
    (root / "packages").mkdir(parents=True)
    data = b"synthetic signed worker package"
    digest = hashlib.sha256(data).hexdigest()
    (root / "manifest.json").write_bytes(b"{}")
    (root / "manifest.sig").write_bytes(b"s" * 64)
    (root / "packages" / f"{digest}.zip").write_bytes(data)
    api = client(tmp_path)
    path = "/api/v1/worker/base-releases"
    assert api.get(f"{path}/manifest").status_code == 401
    assert api.get(f"{path}/blobs/{digest}").status_code == 401
    headers = {"Authorization": "Bearer synthetic-device"}
    response = api.get(f"{path}/manifest", headers=headers)
    assert response.status_code == 200 and base64.b64decode(response.json()["signature"]) == b"s" * 64
    blob = api.get(f"{path}/blobs/{digest}", headers=headers)
    assert blob.status_code == 200 and blob.content == data and blob.headers["cache-control"] == "no-store"
    assert api.get(f"{path}/blobs/not-a-digest", headers=headers).status_code == 404


def test_missing_or_invalid_release_is_not_served(tmp_path):
    headers = {"Authorization": "Bearer synthetic-device"}
    assert client(None).get("/api/v1/worker/base-releases/manifest", headers=headers).status_code == 503
    root = tmp_path / "worker-base"
    root.mkdir()
    (root / "manifest.json").write_bytes(b"{}")
    (root / "manifest.sig").write_bytes(b"short")
    assert client(tmp_path).get("/api/v1/worker/base-releases/manifest", headers=headers).status_code == 404
