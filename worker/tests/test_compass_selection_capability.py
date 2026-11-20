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


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('compass_capability_test', ROOT / 'capabilities/douyin_compass_selection/capability.py')
capability = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capability)


def task(operation='rank', **changes):
    values = {'operation': operation, 'correlation_id': str(uuid4()), **changes}
    if operation == 'rank':
        values = {'operation': operation, 'correlation_id': str(uuid4()), 'industry_id': '7', 'category_id': '101,102', 'page_no': 2,
                  'begin_date': '2026/10/03 00:00:00', 'end_date': '2026/10/09 00:00:00', **changes}
    return WorkerTask(task_id=uuid4(), skill_id=capability.SKILL_ID, input=values,
                      lease_until=datetime.now(UTC) + timedelta(seconds=60),
                      local_shops=[LocalShopContext(local_shop_id='local-a', platform='douyin', platform_shop_id='123')])


class Host:
    device_id = uuid4()

    def __init__(self, payload, status=200):
        self.requests = []
        self._transport = httpx.MockTransport(lambda request: (self.requests.append(request),
                                                    httpx.Response(status, json=payload))[1])

    async def read_session(self, local_id, platform_id):
        assert (local_id, platform_id) == ('local-a', '123')
        return SimpleNamespace(user_agent='synthetic-agent', cookies=[
            SimpleNamespace(name='sessionid', value=SecretStr('synthetic-cookie'), domain='.jinritemai.com', path='/'),
            SimpleNamespace(name='s_v_web_id', value=SecretStr('synthetic-fingerprint'), domain='.jinritemai.com', path='/'),
        ])

    def sign_compass(self, query, user_agent):
        assert user_agent == 'synthetic-agent'
        assert 'synthetic-cookie' not in query
        return 'synthetic-signature'


def rank_payload():
    return {'st': 0, 'data': {'page_result': {'page_no': 2, 'page_size': 10, 'total': 20},
                              'data_result': [{'product_info': {'id': '1000000000000000001', 'name': '测试商品',
                                                               'rank': 11, 'newly_on_ranking': True,
                                                               'internal_secret': 'not-for-output'},
                                               'pay_amt': {'value_range': [{'value': 0, 'unit': 'price'},
                                                                           {'value': 100, 'unit': 'price'}]}}]}}


def test_rank_uses_one_locally_mapped_shop_and_returns_only_business_fields():
    host = Host(rank_payload())
    result = asyncio.run(capability.execute(host, task()))
    assert result.status is ExecutionStatus.SUCCESS
    assert len(host.requests) == 1
    request = host.requests[0]
    assert request.url.host == 'compass.jinritemai.com'
    assert request.url.path.endswith('/product_rank/video_bring_good')
    query = parse_qs(request.url.query.decode('ascii'), keep_blank_values=True)
    assert query['category_id'] == ['101,102'] and query['page_no'] == ['2']
    assert query['fp'] == ['synthetic-fingerprint'] and query['a_bogus'] == ['synthetic-signature']
    assert result.result['data']['data_result'][0]['product_info']['id'] == '1000000000000000001'
    assert result.result['data']['data_result'][0]['pay_amt']['value_range'][0]['value'] == 0
    assert 'synthetic-cookie' not in json.dumps(result.result)
    assert 'synthetic-fingerprint' not in json.dumps(result.result)
    assert 'not-for-output' not in json.dumps(result.result)


def test_categories_return_the_actual_tree_and_basic_requires_the_same_product():
    host = Host({'st': '0', 'data': {'industry_id': 7, 'cate_list': [
        {'cate_id': 7, 'cate_name': '行业', 'children': [{'cate_id': 101, 'cate_name': '父级', 'children': []}]}
    ]}})
    result = asyncio.run(capability.execute(host, task('categories')))
    assert result.status is ExecutionStatus.SUCCESS
    assert result.result['data']['nodes'][0]['children'][0]['category_id'] == '101'
    host = Host({'st': 0, 'data': {'product_id': '999', 'cid_info': ['测试类目']}})
    result = asyncio.run(capability.execute(host, task('basic', product_id='123')))
    assert result.error_code == 'PLATFORM_RESPONSE_INVALID'


def test_basic_preserves_zero_and_unknown_rate_separately():
    host = Host({'st': 0, 'data': {'product_id': '123', 'bad_comment_rate': {'value': {'value': 0, 'unit': 4}}}})
    result = asyncio.run(capability.execute(host, task('basic', product_id='123')))
    assert result.result['data']['bad_comment_rate']['value']['value'] == 0
    host = Host({'st': 0, 'data': {'product_id': '123'}})
    result = asyncio.run(capability.execute(host, task('basic', product_id='123')))
    assert 'bad_comment_rate' not in result.result['data']


def test_business_rejection_and_network_failure_do_not_mark_session_expired():
    host = Host({'st': 600002, 'msg': '平台暂不可用'})
    result = asyncio.run(capability.execute(host, task()))
    assert result.error_code == 'PLATFORM_BUSINESS_REJECTED' and result.result['platform_code'] == 600002
    host = Host({'st': 1, 'msg': '请先登录'}, status=503)
    result = asyncio.run(capability.execute(host, task()))
    assert result.error_code == 'PLATFORM_REQUEST_FAILED'
    host = Host({'st': 1, 'msg': '请先登录'}, status=401)
    assert asyncio.run(capability.execute(host, task())).error_code == 'SHOP_SESSION_EXPIRED'


def test_rejects_bad_parameters_or_wrong_shop_before_any_request():
    host = Host(rank_payload())
    result = asyncio.run(capability.execute(host, task(category_id='101,0')))
    assert result.error_code == 'SKILL_INPUT_INVALID' and not host.requests
    no_shop = task()
    no_shop.local_shops = []
    result = asyncio.run(capability.execute(host, no_shop))
    assert result.error_code == 'SKILL_INPUT_INVALID' and not host.requests


def test_local_signer_reuses_the_existing_reviewed_pure_algorithm(monkeypatch):
    assert (ROOT / 'app/compass_signer.py').read_bytes() == (ROOT.parent / 'backend/app/integrations/douyin_signer/pure_algorithm.py').read_bytes()
    calls = []
    monkeypatch.setattr('app.capability_host.generate_compass_signature', lambda *args, **kwargs: calls.append((args, kwargs)) or 'signature')
    assert CapabilityHost.sign_compass('page_no=1', 'agent') == 'signature'
    assert calls == [(('page_no=1', 'agent'), {'aid': 6383, 'page_id': 6241})]
    with pytest.raises(ValueError):
        CapabilityHost.sign_compass('page_no=1', 'bad\r\nheader')


def test_signed_capability_loads_and_its_schema_is_supported_by_the_existing_backend():
    entry = ROOT / 'capabilities/douyin_compass_selection/capability.py'
    module = _load_entry(capability.SKILL_ID, entry.read_bytes())
    path = ROOT.parent / 'backend/app/modules/workers/business_skill_schema.py'
    spec = importlib.util.spec_from_file_location('selection_business_schema_test', path)
    schema_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = schema_module
    try:
        spec.loader.exec_module(schema_module)
        assert schema_module.analyze_business_skill_input_schema(module.INPUT_SCHEMA).status == 'available'
    finally:
        sys.modules.pop(spec.name, None)
