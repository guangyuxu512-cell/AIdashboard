from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.database import get_database_session
from app.main import create_app
from app.modules.devices.exceptions import DeviceNotFoundError
from app.modules.devices.service import DeviceService
from app.modules.workers.auth import get_worker_principal
from app.modules.workers.precheck_contract import LocalShopSummary


def test_local_inventory_uses_only_matching_worker_observations():
    device_id = uuid4()
    now = datetime.now(UTC)
    repository = Mock()
    repository.get_for_actor.return_value = object()
    session = Mock()
    session.get.return_value = SimpleNamespace(
        available=True,
        last_discovered_at=now,
        shops=[
            {"localShopId": "local-a", "platformShopId": "100", "shopName": "A",
             "platform": "douyin", "sessionStored": True, "sessionRevision": "new"},
            {"localShopId": "local-b", "platformShopId": "200", "shopName": "B",
             "platform": "douyin", "sessionStored": True, "sessionRevision": "same"},
            {"localShopId": "local-c", "platformShopId": "300", "shopName": "C",
             "platform": "douyin", "sessionStored": False},
            {"localShopId": "local-d", "platformShopId": "400", "shopName": "D",
             "platform": "douyin", "sessionStored": True, "sessionRevision": "same"},
        ],
    )
    session.execute.return_value.all.return_value = [
        ({"local_shop_id": "local-a", "platform_shop_id": "100", "_session_revision": "old"},
         "failed", "SHOP_SESSION_EXPIRED", now),
        ({"local_shop_id": "local-b", "platform_shop_id": "200", "_session_revision": "same"},
         "failed", "SHOP_SESSION_EXPIRED", now),
        ({"local_shop_id": "local-d", "platform_shop_id": "400", "_session_revision": "same"},
         "failed", "PLATFORM_NETWORK_ERROR", now),
    ]
    result = DeviceService(session, repository=repository).get_local_shops(Mock(), device_id)
    assert result.available
    assert [item.session_status for item in result.shops] == [
        "unknown", "invalid", "reauthorization_required", "unknown",
    ]
    assert "sessionRevision" not in result.model_dump_json()


def test_local_inventory_checks_device_access_before_reading():
    repository = Mock()
    repository.get_for_actor.return_value = None
    session = Mock()
    with pytest.raises(DeviceNotFoundError):
        DeviceService(session, repository=repository).get_local_shops(Mock(), uuid4())
    session.get.assert_not_called()


def test_stale_inventory_is_not_reported_as_current():
    repository = Mock()
    repository.get_for_actor.return_value = object()
    session = Mock()
    session.get.return_value = SimpleNamespace(
        available=True,
        last_discovered_at=datetime.now(UTC) - timedelta(minutes=6),
        shops=[],
    )
    session.execute.return_value.all.return_value = []
    result = DeviceService(session, repository=repository).get_local_shops(Mock(), uuid4())
    assert not result.available


def test_stale_success_does_not_resurrect_an_older_expiry():
    now = datetime.now(UTC)
    repository = Mock()
    repository.get_for_actor.return_value = object()
    session = Mock()
    session.get.return_value = SimpleNamespace(
        available=True, last_discovered_at=now,
        shops=[{"localShopId": "a", "platformShopId": "1", "shopName": "A",
                "platform": "douyin", "sessionStored": True, "sessionRevision": "same"}],
    )
    params = {"local_shop_id": "a", "platform_shop_id": "1", "_session_revision": "same"}
    session.execute.return_value.all.return_value = [
        (params, "success", None, now - timedelta(minutes=31)),
        (params, "failed", "SHOP_SESSION_EXPIRED", now - timedelta(minutes=45)),
    ]
    result = DeviceService(session, repository=repository).get_local_shops(Mock(), uuid4())
    assert result.shops[0].session_status == "unknown"


def test_current_worker_observation_is_used_and_stale_valid_is_unknown():
    now = datetime.now(UTC)
    repository = Mock()
    repository.get_for_actor.return_value = object()
    session = Mock()
    base = {"platform": "douyin", "sessionStored": True, "sessionRevision": "a" * 64}
    session.get.return_value = SimpleNamespace(available=True, last_discovered_at=now, shops=[
        {**base, "localShopId": "a", "platformShopId": "1", "shopName": "A",
         "sessionStatus": "valid", "sessionCheckedAt": now.isoformat()},
        {**base, "localShopId": "b", "platformShopId": "2", "shopName": "B",
         "sessionStatus": "invalid", "sessionCheckedAt": now.isoformat()},
        {**base, "localShopId": "c", "platformShopId": "3", "shopName": "C",
         "sessionStatus": "valid", "sessionCheckedAt": (now - timedelta(minutes=31)).isoformat()},
    ])
    session.execute.return_value.all.return_value = []
    result = DeviceService(session, repository=repository).get_local_shops(Mock(), uuid4())
    assert [item.session_status for item in result.shops] == ["valid", "invalid", "unknown"]
    assert result.shops[0].status_observed_at == now
    assert "sessionRevision" not in result.model_dump_json()


def test_general_login_cannot_clear_category_auth_failure_for_the_same_snapshot():
    now = datetime.now(UTC)
    repository = Mock()
    repository.get_for_actor.return_value = object()
    session = Mock()
    session.get.return_value = SimpleNamespace(available=True, last_discovered_at=now, shops=[{
        "localShopId": "a", "platformShopId": "1", "shopName": "A", "platform": "douyin",
        "sessionStored": True, "sessionRevision": "same", "sessionStatus": "valid",
        "sessionCheckedAt": now.isoformat(),
    }])
    session.execute.return_value.all.return_value = [
        ({"local_shop_id": "a", "platform_shop_id": "1", "_session_revision": "same"},
         "failed", "SHOP_SESSION_EXPIRED", now - timedelta(minutes=1)),
    ]
    result = DeviceService(session, repository=repository).get_local_shops(Mock(), uuid4())
    assert result.shops[0].session_status == "invalid"


def test_worker_observation_must_match_a_saved_snapshot():
    values = {"localShopId": "a", "platformShopId": "1", "shopName": "A", "platform": "douyin",
              "sessionStored": True, "sessionRevision": "a" * 64,
              "sessionStatus": "valid", "sessionCheckedAt": datetime.now(UTC).isoformat()}
    assert LocalShopSummary.model_validate(values).session_status == "valid"
    for invalid in ({**values, "sessionRevision": None}, {**values, "sessionStored": False},
                    {**values, "sessionCheckedAt": None}, {**values, "platform": "pdd"},
                    {**values, "cookie": "synthetic"}):
        with pytest.raises(ValueError):
            LocalShopSummary.model_validate(invalid)


def test_worker_inventory_is_independent_of_product_precheck_switch():
    app = create_app()
    device_id = uuid4()
    app.dependency_overrides[get_settings] = lambda: Settings(
        application_worker_precheck_enabled=False,
    )
    app.dependency_overrides[get_worker_principal] = lambda: SimpleNamespace(
        device_id=device_id,
    )
    app.dependency_overrides[get_database_session] = lambda: Mock()
    with patch("app.modules.workers.precheck_api.save_rpa_inventory") as save:
        with TestClient(app) as client:
            response = client.put(
                "/api/v1/worker/rpa-shop-inventory",
                json={"available": False},
            )
    assert response.status_code == 204
    assert save.call_args.args[1] == device_id
