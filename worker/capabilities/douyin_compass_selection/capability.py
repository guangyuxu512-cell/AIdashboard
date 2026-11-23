"""Read-only Compass selection using one Worker-local RPA shop session."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
import math
import re
from typing import Literal
from urllib.parse import parse_qsl, urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.contracts import ExecutionResult, ExecutionStatus


SKILL_ID = 'douyin.compass_selection'
_HOST = 'compass.jinritemai.com'
_PATHS = {
    'categories': '/compass_api/config_center/category/cate_list',
    'rank': '/compass_api/shop/product/product_rank/video_bring_good',
    'basic': '/compass_api/shop/product/compete_product_detail/basic_info',
}
_REFERER = 'https://compass.jinritemai.com/shop/chance/merchandise-product-rank?rank_type=3&from_page=%2Fshop%2Fmerchandise-traffic'
_MAX_RESPONSE = 3 * 1024 * 1024
_LOGIN_MESSAGES = {'未登录', '用户未登录', '请先登录', '请重新登录', '登录失效', '登录已失效',
                   '登录过期', '登录已过期', '登录状态失效', '登录状态已失效', '登录状态已过期',
                   '登录失效请重新登录', '登录过期请重新登录', '登录状态已失效请重新登录',
                   '登录状态已过期请重新登录', 'sessionexpired', 'loginrequired', 'notloggedin'}


class SelectionInput(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    correlation_id: str = Field(pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    operation: Literal['categories', 'rank', 'basic']
    industry_id: str = Field(default='', max_length=32)
    category_id: str = Field(default='', max_length=98)
    brand_type: Literal['-1', '0', '1'] = '-1'
    price_bin: str = Field(default='不限', max_length=27)
    begin_date: str = Field(default='', max_length=19)
    end_date: str = Field(default='', max_length=19)
    date_type: Literal['1', '20', '21', '23'] = '21'
    page_no: int = Field(default=1, ge=1, le=20, strict=True)
    product_id: str = Field(default='', max_length=32)

    @model_validator(mode='after')
    def validate_business(self):
        if self.operation == 'basic':
            if re.fullmatch(r'[0-9]{1,32}', self.product_id) is None:
                raise ValueError('invalid product id')
        elif self.operation == 'rank':
            ids = self.category_id.split(',')
            if (re.fullmatch(r'[0-9]{1,32}', self.industry_id) is None or not self.industry_id.strip('0')
                    or not 1 <= len(ids) <= 3 or len(set(ids)) != len(ids)
                    or self.industry_id in ids or any(re.fullmatch(r'[0-9]{1,32}', i) is None or not i.strip('0') for i in ids)):
                raise ValueError('invalid category path')
            if self.price_bin != '不限':
                match = re.fullmatch(r'([0-9]{1,10}(?:\.[0-9]{1,2})?)-([0-9]{1,10}(?:\.[0-9]{1,2})?)', self.price_bin)
                if not match:
                    raise ValueError('invalid price')
                try:
                    if Decimal(match[1]) > Decimal(match[2]):
                        raise ValueError('invalid price')
                except InvalidOperation:
                    raise ValueError('invalid price') from None
            try:
                start = datetime.strptime(self.begin_date, '%Y/%m/%d 00:00:00')
                end = datetime.strptime(self.end_date, '%Y/%m/%d 00:00:00')
                if (start.strftime('%Y/%m/%d 00:00:00') != self.begin_date
                        or end.strftime('%Y/%m/%d 00:00:00') != self.end_date
                        or (end - start).days != {'1': 0, '20': 0, '21': 6, '23': 29}[self.date_type]):
                    raise ValueError('invalid dates')
            except (ValueError, KeyError):
                raise ValueError('invalid dates') from None
        return self


INPUT_SCHEMA = SelectionInput.model_json_schema(mode='validation')


def _failure(code, message, **safe):
    return ExecutionResult(status=ExecutionStatus.FAILED, result={'kind': SKILL_ID, **safe},
                           error_code=code, error_message=message)


def _cookie_jar(session):
    cookies = httpx.Cookies()
    for cookie in session.cookies:
        cookies.set(cookie.name, cookie.value.get_secret_value(), domain=cookie.domain, path=cookie.path)
    return cookies


def _business_query(data):
    if data.operation == 'categories':
        return [('level', '4'), ('scene', '6'), ('default_cate_to_level', '2')]
    if data.operation == 'basic':
        return [('product_id', data.product_id)]
    return [
        ('page_no', str(data.page_no)), ('page_size', '10'), ('industry_id', data.industry_id),
        ('category_id', data.category_id), ('brand_type', data.brand_type), ('price_bin', data.price_bin),
        ('search_info', ''), ('rank_data_type', '1'), ('begin_date', data.begin_date),
        ('end_date', data.end_date), ('date_type', data.date_type), ('activity_id', ''),
    ]


def _identifier(value):
    if type(value) is int and value >= 0:
        return str(value)
    return value if isinstance(value, str) and value.strip() else None


def _category(node, depth=0):
    if depth > 8 or not isinstance(node, dict):
        raise ValueError('invalid category')
    category_id, name, children = _identifier(node.get('cate_id')), node.get('cate_name'), node.get('children')
    if not category_id or not isinstance(name, str) or not name.strip() or not isinstance(children, list):
        raise ValueError('invalid category')
    return {'category_id': category_id, 'name': name, 'children': [_category(child, depth + 1) for child in children]}


def _public_image(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username or parsed.password
                or parsed.fragment or any(key.lower() in {'cookie', 'token', 'mstoken', 'a_bogus',
                       'authorization', 'sessionid', 'verifyfp', 'fp', '_lid'} for key, _ in parse_qsl(parsed.query))):
            return None
    except ValueError:
        return None
    return value


def _metric(row, key):
    value = row.get(key)
    if value is None:
        return value
    if not isinstance(value, dict) or not isinstance(value.get('value_range'), list):
        return {}
    return {'value_range': [{'value': _safe_number(part.get('value')),
                             'unit': part.get('unit') if type(part.get('unit')) in {int, str} else None}
                            if isinstance(part, dict) else None for part in value['value_range'][:3]]}


def _safe_number(value):
    if value is None or type(value) is int or (type(value) is float and math.isfinite(value)):
        return value
    return 'invalid'


def _project(data, operation, expected):
    if not isinstance(data, dict):
        raise ValueError('invalid data')
    if operation == 'categories':
        nodes = data.get('cate_list')
        if not isinstance(nodes, list):
            raise ValueError('invalid categories')
        return {'nodes': [_category(node) for node in nodes], 'industry_id': _identifier(data.get('industry_id')),
                'industry_name': data.get('industry_name') if isinstance(data.get('industry_name'), str) else None,
                'selected_category_id': _identifier(data.get('cate_id'))}
    if operation == 'basic':
        product_id = data.get('product_id')
        if not isinstance(product_id, str) or product_id != expected.product_id:
            raise ValueError('product identity mismatch')
        output = {'product_id': product_id}
        if 'cid_info' in data:
            value = data['cid_info']
            output['cid_info'] = (value if value is None or isinstance(value, list)
                                  and all(isinstance(v, str) and len(v) <= 100 for v in value) else {})
        if 'first_on_shelf_time' in data:
            value = data['first_on_shelf_time']
            output['first_on_shelf_time'] = value if value is None or isinstance(value, str) and len(value) <= 30 else {}
        if 'bad_comment_rate' in data:
            value = data['bad_comment_rate']
            nested = value.get('value') if isinstance(value, dict) else None
            if isinstance(nested, dict):
                projected = {}
                if 'value' in nested:
                    projected['value'] = _safe_number(nested['value'])
                if 'unit' in nested:
                    projected['unit'] = nested['unit'] if type(nested['unit']) in {int, str} else None
                output['bad_comment_rate'] = {'value': projected}
            else:
                output['bad_comment_rate'] = None if value is None else {}
        return output
    rows, page = data.get('data_result'), data.get('page_result')
    if (not isinstance(rows, list) or len(rows) > 10 or not isinstance(page, dict)
            or type(page.get('page_no')) is not int or page['page_no'] != expected.page_no
            or type(page.get('page_size')) is not int or page['page_size'] != 10
            or type(page.get('total')) is not int or page['total'] < 0):
        raise ValueError('invalid rank page')
    result = []
    for row in rows:
        info = row.get('product_info') if isinstance(row, dict) else None
        if not isinstance(info, dict) or not isinstance(info.get('id'), str) or re.fullmatch(r'[0-9]{1,32}', info['id']) is None:
            raise ValueError('invalid product id')
        projected = {'id': info['id']}
        for key in ('name', 'price_bin'):
            if isinstance(info.get(key), str):
                projected[key] = info[key]
        if type(info.get('rank')) is int and info['rank'] >= 0:
            projected['rank'] = info['rank']
        if type(info.get('newly_on_ranking')) is bool:
            projected['newly_on_ranking'] = info['newly_on_ranking']
        leaf = _identifier(info.get('leaf_category_id'))
        if leaf is not None:
            projected['leaf_category_id'] = leaf
        image = _public_image(info.get('image_url'))
        if image is not None:
            projected['image_url'] = image
        shops = info.get('shop_list')
        if isinstance(shops, list):
            projected['shop_list'] = [{'shop_id': _identifier(shop.get('shop_id')),
                                       'shop_name': shop.get('shop_name') if isinstance(shop.get('shop_name'), str) else None}
                                      for shop in shops if isinstance(shop, dict) and _identifier(shop.get('shop_id'))]
        product = {'product_info': projected}
        for key in ('pay_amt', 'pay_combo_cnt', 'product_click_cnt', 'video_cnt'):
            if key in row:
                product[key] = _metric(row, key)
        result.append(product)
    return {'page_result': {'page_no': page['page_no'], 'page_size': page['page_size'], 'total': page['total']},
            'data_result': result}


async def execute(host, task):
    try:
        params = SelectionInput.model_validate(task.input)
        if len(task.local_shops) != 1:
            raise ValueError('one mapped shop is required')
        shop = task.local_shops[0]
        if shop.platform != 'douyin' or not shop.platform_shop_id:
            raise ValueError('invalid mapped shop')
    except (ValidationError, ValueError, AttributeError):
        return _failure('SKILL_INPUT_INVALID', '选品任务或店铺映射无效')
    try:
        session = await host.read_session(shop.local_shop_id, shop.platform_shop_id)
        cookies = _cookie_jar(session)
        target = f'https://{_HOST}{_PATHS[params.operation]}'
        cookie_request = httpx.Request('GET', target, cookies=cookies)
        cookie_header = cookie_request.headers.get('cookie', '')
        if not cookie_header:
            raise ValueError('no matching session')
    except Exception as error:
        code = getattr(error, 'code', 'RPA_SESSION_UNAVAILABLE')
        if not isinstance(code, str) or re.fullmatch(r'[A-Z][A-Z0-9_]{2,63}', code) is None:
            code = 'RPA_SESSION_UNAVAILABLE'
        return _failure(code, '设备没有可用的本机店铺会话')
    try:
        query = _business_query(params)
        fp = {part.strip().partition('=')[2] for part in cookie_header.split(';')
              if part.strip().partition('=')[0] == 's_v_web_id'}
        if len(fp) == 1 and '' not in fp:
            value = next(iter(fp))
            query.extend([('fp', value), ('verifyFp', value)])
        unsigned = httpx.URL(target, params=query)
        signature = host.sign_compass(unsigned.query.decode('ascii'), session.user_agent)
        signed = unsigned.copy_add_param('a_bogus', signature)
    except Exception:
        return _failure('PLATFORM_SIGNER_FAILED', '罗盘签名未完成')
    try:
        headers = {'accept': 'application/json, text/plain, */*', 'accept-language': 'zh-CN,zh;q=0.9',
                   'agw-js-conv': 'str', 'user-agent': session.user_agent,
                   'referer': 'https://compass.jinritemai.com/shop' if params.operation == 'categories' else _REFERER,
                   'x-e2e-platform': 'compass', 'cookie': cookie_header}
        async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False,
                                     transport=getattr(host, '_transport', None)) as client:
            async with client.stream('GET', signed, headers=headers) as response:
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > _MAX_RESPONSE:
                        raise ValueError('response too large')
                http_status = response.status_code
                payload = json.loads(content)
    except Exception:
        return _failure('PLATFORM_REQUEST_FAILED', '罗盘请求未完成')
    if not isinstance(payload, dict):
        return _failure('PLATFORM_RESPONSE_INVALID', '罗盘返回格式无效', http_status=http_status)
    code = payload.get('st')
    if http_status != 200 or type(code) not in {int, str} or code not in (0, '0'):
        text = payload.get('message', payload.get('msg'))
        normalized = re.sub(r'[\s，。！？、:：!,.；;]+', '', text).lower() if isinstance(text, str) and len(text) <= 120 else ''
        if http_status in (200, 401) and normalized in _LOGIN_MESSAGES:
            return _failure('SHOP_SESSION_EXPIRED', '店铺登录状态已失效', http_status=http_status)
        if http_status != 200:
            return _failure('PLATFORM_REQUEST_FAILED', '罗盘请求未完成', http_status=http_status)
        if type(code) not in {int, str}:
            return _failure('PLATFORM_RESPONSE_INVALID', '罗盘返回格式无效', http_status=http_status)
        safe_code = code if type(code) is int or (isinstance(code, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', code)) else None
        if params.operation == 'basic' and code in (600002, '600002') and normalized == '无权限':
            # Preserve the existing error/result contract while retaining the
            # platform's explicit permission signal for store failover.
            return _failure('PLATFORM_BUSINESS_REJECTED', '平台返回无权限',
                            http_status=http_status, platform_code=safe_code)
        return _failure('PLATFORM_BUSINESS_REJECTED', '罗盘请求被平台拒绝', http_status=http_status, platform_code=safe_code)
    try:
        data = _project(payload.get('data'), params.operation, params)
        result = {'kind': SKILL_ID, 'operation': params.operation, 'platform_shop_id': shop.platform_shop_id, 'data': data}
        if len(json.dumps(result, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')) > _MAX_RESPONSE:
            raise ValueError('result too large')
        return ExecutionResult(status=ExecutionStatus.SUCCESS, result=result)
    except (ValueError, TypeError, RecursionError):
        return _failure('PLATFORM_RESPONSE_INVALID', '罗盘返回格式无效')
