from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient, Response

from app.main import create_app
from app.modules.devices.api import get_worker_service as get_device_worker_service
from app.modules.workers.api import get_worker_service as get_worker_api_service
from app.modules.workers.auth import get_worker_provisioning_principal
from app.modules.workers.schemas import (
    WorkerCredentialRead,
    WorkerProvisioningRead,
    WorkerTokenIssuedRead,
)
from app.modules.workers.service import WorkerPrincipal


DEVICE_ID = uuid4()


class ApiWorkerCredentialService:
    def __init__(self) -> None:
        self.status = "not_issued"
        self.issued_at: datetime | None = None
        self.sequence = 0

    def get_credential(self, device_id: UUID) -> WorkerCredentialRead:
        return WorkerCredentialRead(
            device_id=device_id,
            status=self.status,
            issued_at=self.issued_at,
        )

    def issue_credential(self, device_id: UUID) -> WorkerTokenIssuedRead:
        return self._issued(device_id)

    def rotate_credential(self, device_id: UUID) -> WorkerTokenIssuedRead:
        return self._issued(device_id)

    def disable_token(self, device_id: UUID) -> None:
        del device_id
        self.status = "revoked"

    def get_provisioning(self, principal: WorkerPrincipal) -> WorkerProvisioningRead:
        return WorkerProvisioningRead(
            device_id=principal.device_id,
            device_display_name="Provisioned PC",
            device_enabled=True,
        )

    def _issued(self, device_id: UUID) -> WorkerTokenIssuedRead:
        self.sequence += 1
        self.status = "issued"
        self.issued_at = datetime.now(UTC)
        return WorkerTokenIssuedRead(
            device_id=device_id,
            status="issued",
            issued_at=self.issued_at,
            token=f"ccw_one_time_{self.sequence}",
        )


def request(
    application: object,
    method: str,
    path: str,
    **kwargs: object,
) -> Response:
    async def send() -> Response:
        transport = ASGITransport(app=application)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_worker_token_is_only_returned_by_issue_and_rotate_responses() -> None:
    application = create_app()
    service = ApiWorkerCredentialService()
    application.dependency_overrides[get_device_worker_service] = lambda: service

    issued = request(
        application,
        "POST",
        f"/api/v1/devices/{DEVICE_ID}/worker-credential/issue",
    )
    read = request(
        application,
        "GET",
        f"/api/v1/devices/{DEVICE_ID}/worker-credential",
    )
    rotated = request(
        application,
        "POST",
        f"/api/v1/devices/{DEVICE_ID}/worker-credential/rotate",
    )
    revoked = request(
        application,
        "POST",
        f"/api/v1/devices/{DEVICE_ID}/worker-credential/revoke",
    )

    assert issued.status_code == 200
    assert issued.headers["cache-control"] == "no-store"
    assert issued.json()["token"] == "ccw_one_time_1"
    assert "token" not in read.json()
    assert "token_hash" not in read.json()
    assert rotated.headers["cache-control"] == "no-store"
    assert rotated.json()["token"] == "ccw_one_time_2"
    assert revoked.status_code == 204


def test_token_only_provisioning_returns_device_identity_without_device_header() -> None:
    application = create_app()
    service = ApiWorkerCredentialService()
    application.dependency_overrides[get_worker_api_service] = lambda: service
    application.dependency_overrides[get_worker_provisioning_principal] = lambda: (
        WorkerPrincipal(device_id=DEVICE_ID)
    )

    response = request(
        application,
        "GET",
        "/api/v1/worker/provisioning",
        headers={"Authorization": "Bearer ccw_valid"},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "device_id": str(DEVICE_ID),
        "device_display_name": "Provisioned PC",
        "device_enabled": True,
    }
