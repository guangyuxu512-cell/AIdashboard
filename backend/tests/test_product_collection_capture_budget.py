"""A Dispatch's finite phone budget survives configuration changes and replay."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.modules.product_collection.contracts import canonical_sha256
from app.modules.product_collection.dispatch_service import build_dispatch_command, command_from_dispatch
from app.modules.product_collection.exceptions import ProductCollectionStateConflictError


def _item():
    return SimpleNamespace(platform="douyin", source_product_id="3797024140330926544")


def _historical_hash(dispatch_id, *, recapture=False, max_attempts=3):
    return canonical_sha256({
        "version": 1, "external_job_id": f"pcd_v1_{dispatch_id.hex}",
        "dispatch_id": str(dispatch_id), "source_platform": "douyin",
        "source_product_id": "3797024140330926544", "ingest_mode": "central_ingest_v1",
        "job_type": "product", "recapture": recapture, "priority": 0,
        "max_attempts": max_attempts,
    })


@pytest.mark.parametrize("budget", [1, 2, 3])
@pytest.mark.parametrize("recapture", [False, True])
def test_replay_recovers_frozen_budget_and_recapture_without_current_configuration(budget, recapture):
    item, dispatch_id = _item(), uuid4()
    original = build_dispatch_command(dispatch_id, item, recapture=recapture, max_attempts=budget)
    assert original.payload()["maxAttempts"] == budget
    assert original.canonical_payload_hash == _historical_hash(dispatch_id, recapture=recapture, max_attempts=budget)
    dispatch = SimpleNamespace(
        dispatch_id=dispatch_id, external_job_id=original.external_job_id,
        canonical_payload_hash=original.canonical_payload_hash,
        # Even an initial explicit recapture is identified by its frozen hash.
        dispatch_no=1,
    )
    restored = command_from_dispatch(dispatch, item)
    assert restored.payload() == original.payload()
    changed = build_dispatch_command(dispatch_id, item, recapture=recapture, max_attempts=4 - budget)
    if budget != 2:
        assert changed.canonical_payload_hash != restored.canonical_payload_hash


def test_default_and_historical_dispatch_keep_normal_three_attempt_budget():
    dispatch_id = uuid4()
    original = build_dispatch_command(dispatch_id, _item())
    assert original.max_attempts == 3
    assert original.canonical_payload_hash == _historical_hash(dispatch_id)
    assert Settings(_env_file=None).product_collection_capture_max_attempts == 3


@pytest.mark.parametrize("budget", [0, 4, -1, True, 1.5])
def test_new_dispatch_and_configuration_reject_out_of_contract_budgets(budget):
    with pytest.raises(ValueError):
        build_dispatch_command(uuid4(), _item(), max_attempts=budget)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, product_collection_capture_max_attempts=budget)


def test_isolated_budget_is_read_from_backend_environment(monkeypatch):
    monkeypatch.setenv("BACKEND_PRODUCT_COLLECTION_CAPTURE_MAX_ATTEMPTS", "1")
    assert Settings(_env_file=None).product_collection_capture_max_attempts == 1


@pytest.mark.parametrize("mutation", ["hash", "external_job", "product"])
def test_replay_rejects_payload_drift_instead_of_sending_a_different_budget(mutation):
    item, dispatch_id = _item(), uuid4()
    dispatch = SimpleNamespace(
        dispatch_id=dispatch_id, external_job_id=f"pcd_v1_{dispatch_id.hex}",
        canonical_payload_hash=_historical_hash(dispatch_id, max_attempts=1), dispatch_no=1,
    )
    if mutation == "hash":
        dispatch.canonical_payload_hash = "0" * 64
    elif mutation == "external_job":
        dispatch.external_job_id = "another-external-id"
    else:
        item.source_product_id = "3797024140330926545"
    with pytest.raises(ProductCollectionStateConflictError):
        command_from_dispatch(dispatch, item)
