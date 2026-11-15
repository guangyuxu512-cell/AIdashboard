from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.sessions.application_auth import ClientGrant
from app.modules.workers.precheck_service import WorkerPrecheckService


def grant(**updates):
    return ClientGrant.model_validate({"client_id": "fixture", "token_sha256": "a" * 64,
        "authorized_by_user_id": uuid4(), "enabled": True, **updates})


def test_all_devices_is_opt_in_and_keeps_explicit_exclusion():
    formal, test_device = uuid4(), uuid4()
    dynamic = grant(worker_precheck_enabled=True, all_precheck_devices=True,
                    excluded_precheck_devices=[test_device])
    assert WorkerPrecheckService._authorized_shop(dynamic, formal, "local", "platform")
    assert not WorkerPrecheckService._authorized_shop(dynamic, test_device, "local", "platform")
    original = grant(worker_precheck_enabled=True, device_ids=[formal], all_mapped_shops=[formal])
    assert WorkerPrecheckService._authorized_shop(original, formal, "local", "platform")
    assert not WorkerPrecheckService._authorized_shop(original, test_device, "local", "platform")


def test_all_devices_requires_precheck_opt_in_and_unambiguous_exclusions():
    test_device = uuid4()
    with pytest.raises(ValidationError):
        grant(all_precheck_devices=True)
    with pytest.raises(ValidationError):
        grant(worker_precheck_enabled=True, device_ids=[test_device], all_mapped_shops=[test_device],
              excluded_precheck_devices=[uuid4()])
    with pytest.raises(ValidationError):
        grant(worker_precheck_enabled=True, all_precheck_devices=True,
              device_ids=[test_device], excluded_precheck_devices=[test_device])
