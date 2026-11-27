import asyncio
from datetime import UTC, datetime, timedelta
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from urllib.parse import parse_qs
from uuid import uuid4

import httpx
from pydantic import SecretStr
import pytest

from app.capability_host import CapabilityHost
from app.capability_runtime import _load_entry
from app.contracts import ExecutionStatus, LocalShopContext, WorkerTask
from app.rpa_session_bridge import RpaBridgeError


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / 'capabilities/douyin_merchant_products/capability.py'
spec = importlib.util.spec_from_file_location('merchant_products_test', ENTRY)
capability = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capability)


def task(state='on_sale', **changes):
    return WorkerTask(task_id=uuid4(), skill_id=capability.SKILL_ID,
        input={'correlation_id': str(uuid4()), 'sync_id': str(uuid4()), 'operation': 'list', 'state': state, 'page': 0, **changes},
        lease_until=datetime.now(UTC) + timedelta(seconds=60),
        result_delivery='operations',
        local_shops=[LocalShopContext(local_shop_id='local-a', platform='douyin', platform_shop_id='123')])


class Bridge:
    async def read_session(self, local_id, platform_id):
        assert (local_id, platform_id) == ('local-a', '123')
        return SimpleNamespace(user_agent='synthetic-agent', cookies=[
            SimpleNamespace(name='sessionid', value=SecretStr('synthetic-cookie'), domain='.jinritemai.com', path='/'),
            SimpleNamespace(name='s_v_web_id', value=SecretStr('synthetic-fingerprint'), domain='.jinritemai.com', path='/'),
        ])


def response():
    return {'code': 0, 'total': 1, 'data': [{'product_id': 1234567890123456789, 'name': '示例商品',
        'img': 'https://images.example.test/item.jpg', 'product_url': 'https://fxg.jinritemai.com/item?id=123',
        'private': 'discard-this-field'}]}


@pytest.mark.parametrize(('state', 'tab', 'flag'), [
    ('on_sale', 'onSale', 'is_online'), ('offline', 'offline', 'is_offline'),
    ('forbidden', 'forbidden', 'is_forbidden'), ('draft', 'draft', 'is_drafting'),
])
def test_one_shop_page_is_signed_locally_and_projects_only_safe_fields(monkeypatch, state, tab, flag):
    requests, signatures = [], []
    monkeypatch.setattr('app.capability_host.generate_compass_signature',
        lambda query, user_agent, **kw: signatures.append((query, user_agent, kw)) or 'synthetic-signature')
    host = CapabilityHost(uuid4(), None, Bridge(), transport=httpx.MockTransport(
        lambda request: (requests.append(request), httpx.Response(200, json=response()))[1]))
    result = asyncio.run(capability.execute(host, task(state)))
    assert result.status == ExecutionStatus.SUCCESS
    assert len(requests) == 1
    query = parse_qs(requests[0].url.query.decode(), keep_blank_values=True)
    assert query['tab'] == [tab] and query[flag] == ['1'] and query['pageSize'] == ['20']
    assert signatures[0][1:] == ('synthetic-agent', {'aid': 4272, 'page_id': 6241})
    assert 'synthetic-cookie' not in signatures[0][0]
    page = result.result['data']['data']
    assert page['items'] == [{'product_id': '1234567890123456789', 'name': '示例商品',
        'image_url': 'https://images.example.test/item.jpg', 'product_url': 'https://fxg.jinritemai.com/item?id=123'}]
    for private in ('synthetic-cookie', 'synthetic-fingerprint', 'synthetic-signature', 'discard-this-field'):
        assert private not in json.dumps(result.result)


def test_unsafe_urls_and_missing_optional_images_remain_empty():
    payload = response()
    payload['data'][0].update(img='http://127.0.0.1/image',
                              product_url='https://fxg.jinritemai.com/item?token=private')
    page = capability._project(payload, capability.ProductPageInput(
        correlation_id=str(uuid4()), sync_id=str(uuid4()), state='on_sale', page=0))
    assert page['items'][0]['image_url'] is None
    assert page['items'][0]['product_url'] is None


def test_network_and_unrelated_business_errors_never_claim_expired_session():
    async def execute(payload, status=200):
        host = CapabilityHost(uuid4(), None, Bridge(), transport=httpx.MockTransport(
            lambda request: httpx.Response(status, json=payload)))
        return await capability.execute(host, task())
    assert asyncio.run(execute({'code': 1, 'msg': '未登录'}, status=503)).error_code == 'PLATFORM_REQUEST_FAILED'
    assert asyncio.run(execute({'code': 1, 'msg': '系统繁忙'})).error_code == 'PLATFORM_BUSINESS_REJECTED'
    assert asyncio.run(execute({'code': 1, 'msg': '请先登录'})).error_code == 'SHOP_SESSION_EXPIRED'


def test_session_and_malformed_input_fail_safely_before_platform_request():
    class FailingBridge:
        async def read_session(self, *_args):
            raise RpaBridgeError('RPA_SESSION_UNAVAILABLE')
    host = CapabilityHost(uuid4(), None, FailingBridge(), transport=httpx.MockTransport(
        lambda _request: pytest.fail('no platform call should occur')))
    assert asyncio.run(capability.execute(host, task())).error_code == 'RPA_SESSION_UNAVAILABLE'
    assert asyncio.run(capability.execute(host, task(page=-1))).error_code == 'SKILL_INPUT_INVALID'
    assert asyncio.run(capability.execute(host, task(page_size=101))).error_code == 'SKILL_INPUT_INVALID'
    old_center_task = task().model_copy(update={'result_delivery': 'central'})
    assert asyncio.run(capability.execute(host, old_center_task)).error_code == 'OPERATIONS_DELIVERY_REQUIRED'


def test_capability_schema_is_accepted_by_existing_worker_and_backend():
    module = _load_entry(capability.SKILL_ID, ENTRY.read_bytes())
    path = ROOT.parent / 'backend/app/modules/workers/business_skill_schema.py'
    schema_spec = importlib.util.spec_from_file_location('merchant_business_schema_test', path)
    schema_module = importlib.util.module_from_spec(schema_spec)
    sys.modules[schema_spec.name] = schema_module
    try:
        schema_spec.loader.exec_module(schema_module)
        assert schema_module.analyze_business_skill_input_schema(module.INPUT_SCHEMA).status == 'available'
    finally:
        sys.modules.pop(schema_spec.name, None)


def test_full_product_data_keeps_business_fields_and_removes_session_material():
    payload = response()
    payload['data'][0].update({
        'stock_num': 12,
        'sell_num_30d': 7,
        'skus': [{'sku_id': 9876543210987654321, 'price': 39.5,
                  'cookie': 'do-not-forward', 'access_token': 'do-not-forward',
                  'session_data': 'do-not-forward'}],
        'extra_url': 'https://example.test/item?color=red&token=do-not-forward',
        'relative_url': '//example.test/item?color=red&msToken=do-not-forward',
        'description': 'synthetic-cookie must not leave this computer',
    })
    host = CapabilityHost(uuid4(), None, Bridge(), transport=httpx.MockTransport(
        lambda _request: httpx.Response(200, json=payload)))
    result = asyncio.run(capability.execute(host, task(include_raw=True, page_size=100)))
    assert result.status == ExecutionStatus.SUCCESS
    raw = result.result['data']['data']['items'][0]['platform_data']
    assert raw['stock_num'] == 12 and raw['sell_num_30d'] == 7
    assert raw['skus'] == [{'sku_id': '9876543210987654321', 'price': 39.5}]
    assert raw['extra_url'] == 'https://example.test/item?color=red'
    assert raw['relative_url'] == '//example.test/item?color=red'
    assert raw['description'] == '[REDACTED]'
    serialized = json.dumps(result.result)
    assert 'synthetic-cookie' not in serialized and 'do-not-forward' not in serialized


def test_full_page_can_exceed_normal_small_skill_result_limit():
    payload = {'code': 0, 'total': 100, 'data': [
        {'product_id': i + 1, 'name': f'商品{i}', 'description': 'a' * 11000}
        for i in range(100)
    ]}
    host = CapabilityHost(uuid4(), None, Bridge(), transport=httpx.MockTransport(
        lambda _request: httpx.Response(200, json=payload)))
    result = asyncio.run(capability.execute(host, task(include_raw=True, page_size=100)))
    assert result.status == ExecutionStatus.SUCCESS
    assert len(json.dumps(result.result)) > 1024 * 1024
    assert len(result.result['data']['data']['items']) == 100
