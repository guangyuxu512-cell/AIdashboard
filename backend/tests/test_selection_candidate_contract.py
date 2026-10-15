from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.product_selection.basic_contract import SelectionBasicExecution, SelectionBasicRequest, BasicInfoStatus
from app.modules.product_selection.basic_service import basic_values_and_status
from app.modules.product_selection.result_contract import SelectionBlockCommand
from app.modules.product_selection.result_service import discovery_key
from app.modules.product_selection.run_contract import SelectionRunOriginal


def test_discovery_identity_is_relative_and_price_normalized_not_a_dated_source_hash():
    team, shop = uuid4(), uuid4()
    base = dict(shop_id=shop, channel="short-video", period="7d", industry_id="7",
        category_ids=("1000009092", "1000009142"), brand="all", price_mode="custom",
        price_above="20", price_below="30", rank_from=1, rank_to=200)
    first = SelectionRunOriginal(**base)
    second = SelectionRunOriginal(**(base | {"price_above": "20.0", "price_below": "30.00"}))
    assert discovery_key(team, first) == discovery_key(team, second)
    assert discovery_key(uuid4(), first) != discovery_key(team, first)
    assert discovery_key(team, first.model_copy(update={"brand": "known"})) != discovery_key(team, first)


def test_basic_fence_is_aware_and_does_not_rewrite_submission_identity():
    with pytest.raises(ValidationError):
        SelectionBasicExecution(rank_started_at=datetime(2026, 10, 15), started_at=datetime.now(UTC), basic_version=1)
    request = SelectionBasicRequest(observation_id=uuid4(), candidate_id=uuid4(), shop_id=uuid4(),
        product_id="3848213119470010668", source_scope_hash="a" * 64)
    executed = request.model_copy(update={"execution": SelectionBasicExecution(
        rank_started_at=datetime.now(UTC), started_at=datetime.now(UTC), basic_version=1)})
    assert request.fingerprint() == executed.fingerprint()
    assert request.product_id == "3848213119470010668"
    with pytest.raises(ValidationError):
        SelectionBlockCommand(blocked="false")


def test_legacy_unknown_basic_success_time_is_not_filled_with_now():
    at = datetime.now(UTC)
    row = SimpleNamespace(basic_info_status=None, basic_info_retrieved_at=None)
    _, partial, status = basic_values_and_status(row, basic=None, error=None, started_at=at, at=at)
    assert partial and status.category_path.last_success_at is None
    with pytest.raises(ValidationError):
        BasicInfoStatus.model_validate(status.model_dump() | {"platform_business_code": True})
