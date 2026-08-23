from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.devices.models import Device
from app.modules.workers.exceptions import (
    WorkerAuthenticationError,
    WorkerCredentialStateConflictError,
)
from app.modules.workers.models import WorkerDeviceCredential
from app.modules.workers.security import hash_worker_token
from app.modules.workers.service import WorkerPrincipal, WorkerService
from tests.support import FakeSession


class FakeCredentialRepository:
    def __init__(self, device: Device) -> None:
        self.device = device
        self.credential: WorkerDeviceCredential | None = None

    def get_device(self, device_id: object) -> Device | None:
        return self.device if device_id == self.device.device_id else None

    def get_credential(self, device_id: object) -> WorkerDeviceCredential | None:
        return self.credential if device_id == self.device.device_id else None

    def get_credential_by_token(self, token: str) -> WorkerDeviceCredential | None:
        if self.credential and self.credential.token_hash == hash_worker_token(token):
            return self.credential
        return None

    def add_credential(self, credential: WorkerDeviceCredential) -> None:
        credential.created_at = datetime.now(UTC)
        credential.updated_at = credential.created_at
        self.credential = credential


def test_worker_credential_issue_rotate_revoke_and_provisioning() -> None:
    device = Device(device_id=uuid4(), display_name="New Worker PC", enabled=True)
    repository = FakeCredentialRepository(device)
    service = WorkerService(  # type: ignore[arg-type]
        FakeSession(),
        repository,  # type: ignore[arg-type]
    )

    assert service.get_credential(device.device_id).status == "not_issued"
    first = service.issue_token(device.device_id)
    assert repository.credential is not None
    assert repository.credential.token_hash == hash_worker_token(first)
    assert first not in repository.credential.token_hash
    assert service.authenticate_token(first) == WorkerPrincipal(
        device_id=device.device_id,
    )
    provisioning = service.get_provisioning(service.authenticate_token(first))
    assert provisioning.device_id == device.device_id
    assert provisioning.device_display_name == "New Worker PC"

    with pytest.raises(WorkerCredentialStateConflictError):
        service.issue_token(device.device_id)

    second = service.rotate_token(device.device_id)
    assert second != first
    with pytest.raises(WorkerAuthenticationError):
        service.authenticate_token(first)
    assert service.authenticate_token(second).device_id == device.device_id

    service.disable_token(device.device_id)
    assert service.get_credential(device.device_id).status == "revoked"
    with pytest.raises(WorkerAuthenticationError):
        service.authenticate_token(second)

    replacement = service.issue_token(device.device_id)
    assert replacement not in {first, second}
    assert service.authenticate_token(replacement).device_id == device.device_id


def test_worker_token_cannot_authenticate_another_device() -> None:
    device = Device(device_id=uuid4(), display_name="PC-A", enabled=True)
    other = Device(device_id=uuid4(), display_name="PC-B", enabled=True)
    repository = FakeCredentialRepository(device)
    service = WorkerService(  # type: ignore[arg-type]
        FakeSession(),
        repository,  # type: ignore[arg-type]
    )
    token = service.issue_token(device.device_id)

    with pytest.raises(WorkerAuthenticationError):
        service.authenticate(other.device_id, token)
