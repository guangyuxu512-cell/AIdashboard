from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.database import get_database_session
from app.main import create_app
from app.modules.devices.exceptions import DeviceNotFoundError
from app.modules.devices.api import get_device_authorized_actor, get_device_service, router as devices_router
from app.modules.devices.schemas import DeviceShopOverviewRead
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
             "platform": "douyin", "sessionStored": True, "sessionRevision": "new", "compassSessionVerified": True},
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
    assert [item.compass_session_verified for item in result.shops] == [True, None, None, None]
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


@pytest.mark.parametrize("success_age", [timedelta(minutes=1), timedelta(minutes=31)])
def test_late_success_does_not_resurrect_an_older_expiry(success_age):
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
        (params, "success", None, now - success_age),
        (params, "failed", "SHOP_SESSION_EXPIRED", now - timedelta(minutes=45)),
    ]
    result = DeviceService(session, repository=repository).get_local_shops(Mock(), uuid4())
    assert result.shops[0].session_status == "invalid"


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


def test_compass_status_is_separate_and_current_observation_controls_legacy_eligibility():
    now = datetime.now(UTC)
    repository = Mock()
    repository.get_for_actor.return_value = object()
    session = Mock()
    base = {"platform": "douyin", "sessionStored": True, "sessionRevision": "a" * 64,
            "sessionStatus": "valid", "sessionCheckedAt": now.isoformat()}
    session.get.return_value = SimpleNamespace(available=True, last_discovered_at=now, shops=[
        {**base, "localShopId": "a", "platformShopId": "1", "shopName": "A",
         "compassSessionVerified": False, "compassSessionStatus": "valid", "compassSessionCheckedAt": now.isoformat()},
        {**base, "localShopId": "b", "platformShopId": "2", "shopName": "B",
         "compassSessionVerified": True, "compassSessionStatus": "invalid", "compassSessionCheckedAt": now.isoformat()},
        {**base, "localShopId": "c", "platformShopId": "3", "shopName": "C",
         "compassSessionVerified": True, "compassSessionStatus": "valid",
         "compassSessionCheckedAt": (now - timedelta(minutes=31)).isoformat()},
    ])
    session.execute.return_value.all.return_value = []
    result = DeviceService(session, repository=repository).get_local_shops(Mock(), uuid4())
    assert [shop.session_status for shop in result.shops] == ["valid", "valid", "valid"]
    assert [shop.compass_session_status for shop in result.shops] == ["valid", "invalid", "unknown"]
    assert [shop.compass_session_verified for shop in result.shops] == [True, False, True]
    assert result.shops[0].compass_status_observed_at == now


def test_overview_uses_only_actor_scoped_devices():
    actor, device_id = Mock(), uuid4()
    repository, session = Mock(), Mock()
    repository.list_all_for_actor.return_value = [SimpleNamespace(
        device_id=device_id, display_name="Workstation", enabled=True,
    )]
    repository.get_for_actor.return_value = object()
    now = datetime.now(UTC)
    session.get.return_value = SimpleNamespace(available=True, last_discovered_at=now, shops=[{
        "localShopId": "a", "platformShopId": "1", "shopName": "A", "platform": "douyin",
        "sessionStored": True, "sessionRevision": "a" * 64,
    }])
    session.execute.return_value.all.return_value = []
    with patch("app.modules.devices.service.WorkerService") as workers:
        workers.return_value.get_runtime_reads.return_value = {}
        result = DeviceService(session, repository=repository).list_shop_overview(actor)
    repository.list_all_for_actor.assert_called_once_with(actor=actor)
    repository.get_for_actor.assert_called_once_with(actor=actor, device_id=device_id)
    assert len(result) == 1 and result[0].device_name == "Workstation"
    assert result[0].shops[0].shop_name == "A"
    assert "sessionRevision" not in result[0].model_dump_json()


def test_overview_route_uses_existing_device_access_and_does_not_collide_with_device_id():
    app = FastAPI()
    app.include_router(devices_router)
    actor, device_id = Mock(), uuid4()
    service = Mock()
    service.list_shop_overview.return_value = [DeviceShopOverviewRead(
        device_id=device_id, device_name="Workstation", device_enabled=True,
        available=False, last_discovered_at=None, shops=[],
    )]
    app.dependency_overrides[get_device_authorized_actor] = lambda: actor
    app.dependency_overrides[get_device_service] = lambda: service
    with TestClient(app) as client:
        response = client.get('/api/v1/devices/local-shop-overview')
    assert response.status_code == 200
    assert response.json()[0]['device_name'] == 'Workstation'
    service.list_shop_overview.assert_called_once_with(actor)


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
    assert LocalShopSummary.model_validate({**values, "compassSessionVerified": True}).compass_session_verified is True
    assert LocalShopSummary.model_validate({**values, "compassSessionStatus": "valid",
        "compassSessionCheckedAt": datetime.now(UTC).isoformat()}).compass_session_status == "valid"
    with pytest.raises(ValueError):
        LocalShopSummary.model_validate({**values, "sessionRevision": None, "compassSessionVerified": True})
    for invalid in ({**values, "sessionRevision": None}, {**values, "sessionStored": False},
                    {**values, "sessionCheckedAt": None}, {**values, "platform": "pdd"},
                    {**values, "compassSessionStatus": "valid"},
                    {**values, "compassSessionStatus": "valid", "compassSessionCheckedAt": datetime.now(UTC).isoformat(), "sessionRevision": None},
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
