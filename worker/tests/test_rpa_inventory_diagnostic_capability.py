import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.capability_runtime import CapabilityRuntime
from app.contracts import ExecutionStatus
from app.rpa_session_bridge import (
    BridgeDiscovery,
    LocalShopInventory,
    RpaAutoBridge,
    RpaBridgeError,
    helper_tree_digest,
)


def _capability():
    path = Path(__file__).parents[1] / 'capabilities/rpa_inventory_diagnostic/capability.py'
    spec = importlib.util.spec_from_file_location('test_rpa_inventory_diagnostic', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _installation(tmp_path):
    root = tmp_path / 'rpa'
    helper = root / 'resources/listing-worker/listing-worker.exe'
    helper.parent.mkdir(parents=True)
    helper.write_bytes(b'synthetic helper')
    (root / '店群自动化软件.exe').write_bytes(b'synthetic rpa')
    data = tmp_path / 'data'
    data.mkdir()
    database = data / 'shop-manager.db'
    database.write_bytes(b'synthetic database')
    discovery = BridgeDiscovery(contractVersion=1, installationId=uuid4(), appVersion='test',
                                helperPath=str(helper), databasePath=str(database))
    marker = data / 'worker-session-bridge.json'
    marker.write_text(discovery.model_dump_json(by_alias=True), encoding='utf-8')
    return data, helper, discovery, marker, database


def _run(bridge, payload=None):
    return asyncio.run(_capability().execute(SimpleNamespace(_rpa=bridge),
                                              SimpleNamespace(input={} if payload is None else payload)))


def test_missing_discovery_is_reported_without_paths(tmp_path):
    result = _run(RpaAutoBridge(tmp_path, lambda: frozenset()))
    assert result.status is ExecutionStatus.SUCCESS
    assert result.result['data']['code'] == 'RPA_DISCOVERY_UNAVAILABLE'
    assert str(tmp_path) not in result.model_dump_json()


def test_reports_signed_helper_mismatch_without_bypassing_it(tmp_path):
    data, _, _, marker, database = _installation(tmp_path)
    before = (marker.read_bytes(), database.read_bytes())
    bridge = RpaAutoBridge(data, lambda: frozenset({'a' * 64}))
    bridge.list_shops = AsyncMock()
    result = _run(bridge)
    assert result.result['data']['code'] == 'RPA_HELPER_UNTRUSTED'
    assert result.result['data']['helper_is_trusted'] is False
    bridge.list_shops.assert_not_called()
    assert before == (marker.read_bytes(), database.read_bytes())


def test_returns_only_counts_for_authorized_inventory(tmp_path):
    data, helper, discovery, _, _ = _installation(tmp_path)
    bridge = RpaAutoBridge(data, lambda: frozenset({helper_tree_digest(helper.parent)}))
    inventory = LocalShopInventory.model_validate({
        'installationId': str(discovery.installation_id),
        'shops': [
            {'localShopId': f'local-{i}', 'platformShopId': str(i), 'shopName': f'private-shop-{i}',
             'platform': 'douyin', 'sessionStored': i != 4}
            for i in range(5)
        ],
    })
    bridge.list_shops = AsyncMock(return_value=inventory)
    result = _run(bridge)
    assert result.result['data']['code'] == 'RPA_INVENTORY_READY'
    assert result.result['data']['shop_count'] == 5
    assert result.result['data']['saved_session_count'] == 4
    rendered = result.model_dump_json()
    assert 'private-shop' not in rendered
    assert 'local-' not in rendered
    assert str(tmp_path) not in rendered
    assert str(discovery.installation_id) not in rendered


def test_reports_helper_error_code_without_exception_details(tmp_path):
    data, helper, _, _, _ = _installation(tmp_path)
    bridge = RpaAutoBridge(data, lambda: frozenset({helper_tree_digest(helper.parent)}))
    bridge.list_shops = AsyncMock(side_effect=RpaBridgeError('RPA_BRIDGE_LIST_EXITED'))
    result = _run(bridge)
    assert result.result['data']['code'] == 'RPA_BRIDGE_LIST_EXITED'
    assert str(tmp_path) not in result.model_dump_json()


def test_unexpected_input_is_not_echoed(tmp_path):
    result = _run(RpaAutoBridge(tmp_path, lambda: frozenset()), {'unexpected': 'synthetic-private'})
    assert result.result['data']['code'] == 'RPA_DIAGNOSTIC_FAILED'
    assert 'synthetic-private' not in result.model_dump_json()


def test_verified_capability_runtime_loads_and_executes_diagnostic(tmp_path):
    class Package:
        skill_id = 'system.rpa_inventory_diagnostic'
        version = '1.0.0'
        entrypoint = Path(__file__).parents[1] / 'capabilities/rpa_inventory_diagnostic/capability.py'

    updater = SimpleNamespace(active_packages=lambda: [Package()])
    runtime = CapabilityRuntime(updater, SimpleNamespace(_rpa=RpaAutoBridge(tmp_path, lambda: frozenset())))
    runtime.validate_entry(Package.skill_id, Package.version, Package.entrypoint.read_bytes())
    runtime.refresh()
    assert [item.skill_id for item in runtime.descriptors()] == [Package.skill_id]
    result = asyncio.run(runtime.execute(SimpleNamespace(skill_id=Package.skill_id, input={})))
    assert result.result['data']['code'] == 'RPA_DISCOVERY_UNAVAILABLE'
    assert str(tmp_path) not in result.model_dump_json()
