"""Pure key/binding checks; runtime queue/fence and platform evidence remain separate."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.product_selection.request_mapping import freeze_short_video_request
from app.modules.product_selection.run_contract import SelectionDateOutcome, SelectionStrategySnapshot
from app.modules.product_selection.strategy_queue_key import SelectionStrategyQueueKey
from tests.test_selection_request_mapping import _original


def request():
    key = uuid4()
    frozen = freeze_short_video_request(_original(), datetime(2026, 10, 14, tzinfo=UTC))
    return frozen.model_copy(update={"strategy": SelectionStrategySnapshot(strategy_id=key, version=1)}), key


def test_key_is_stable_across_strategy_versions_and_mutable_outcome():
    frozen, sid = request()
    raw, base_hash = frozen.model_dump_json(), frozen.fingerprint()
    key = SelectionStrategyQueueKey.from_request(frozen, strategy_id=sid)
    later = frozen.model_copy(update={"strategy": SelectionStrategySnapshot(strategy_id=sid, version=5), "date_outcome": SelectionDateOutcome(state="primary")})
    assert SelectionStrategyQueueKey.from_request(later, strategy_id=sid) == key
    assert SelectionStrategyQueueKey.model_validate_json(key.model_dump_json()).fingerprint() == key.fingerprint()
    assert key.fingerprint() != base_hash
    assert frozen.model_dump_json() == raw and frozen.fingerprint() == base_hash
    assert set(key.model_dump()) == {"version", "base_fingerprint", "strategy_id"}
    assert later.scope == frozen.scope and later.date_plan == frozen.date_plan and later.page_numbers == frozen.page_numbers


@pytest.mark.parametrize("extra", ["submission_key", "occurrence", "strategy_version", "begin_date", "team_id", "nonce"])
def test_extra_metadata_cannot_break_active_dedup(extra):
    frozen, sid = request()
    key = SelectionStrategyQueueKey.from_request(frozen, strategy_id=sid)
    with pytest.raises(ValueError):
        SelectionStrategyQueueKey.model_validate(key.model_dump(mode="json") | {extra: "not-allowed"})


@pytest.mark.parametrize("version", [2, True, "1", 1.0, None])
def test_unsupported_version_is_not_coerced(version):
    frozen, sid = request()
    key = SelectionStrategyQueueKey.from_request(frozen, strategy_id=sid)
    with pytest.raises(ValueError):
        SelectionStrategyQueueKey.model_validate(key.model_dump(mode="json") | {"version": version})


def test_binding_rejects_changed_strategy_and_frozen_basis():
    frozen, sid = request()
    key = SelectionStrategyQueueKey.from_request(frozen, strategy_id=sid)
    key.validate_binding(frozen, strategy_id=sid)
    with pytest.raises(ValueError): key.validate_binding(frozen, strategy_id=uuid4())
    tampered = key.model_copy(update={"base_fingerprint": "0" * 64})
    with pytest.raises(ValueError): tampered.validate_binding(frozen, strategy_id=sid)
    with pytest.raises(ValueError): SelectionStrategyQueueKey.from_request(frozen.model_copy(update={"strategy": None}), strategy_id=sid)


def test_http_command_has_no_queue_key_parameter():
    from app.modules.product_selection.run_contract import SelectionRunCreate
    frozen, sid = request()
    with pytest.raises(ValueError):
        SelectionRunCreate.model_validate(frozen.original.model_dump() | {"submission_key": uuid4(), "queue_key": SelectionStrategyQueueKey.from_request(frozen, strategy_id=sid).model_dump()})
