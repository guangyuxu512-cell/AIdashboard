"""Read a single merchant product page with one Worker-local RPA session."""
from ipaddress import ip_address
import math
import re
from typing import ClassVar, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, ValidationError

from app.contracts import ExecutionResult, ExecutionStatus
from app.skills.sdk import BusinessSkillInput, SkillExecutionError, SkillResult


SKILL_ID = 'douyin.merchant_products'


class ProductPageInput(BusinessSkillInput):
    correlation_id: str = Field(pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    sync_id: str = Field(pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    operation: str = Field(default='list', pattern=r'^list$')
    state: Literal['on_sale', 'offline', 'forbidden', 'draft']
    page: int = Field(ge=0, le=100000, strict=True)
    page_size: int = Field(default=20, ge=1, le=100, strict=True)
    include_raw: bool = Field(default=False, strict=True)


INPUT_SCHEMA = ProductPageInput.model_json_schema(mode='validation')
_SENSITIVE = {'cookie', 'cookies', 'authorization', 'token', 'mstoken', 'a_bogus', 'session',
              'sessionid', 'verifyfp', 'fp', '_lid', '__token'}
_PRIVATE_KEYS = {'account', 'accounts', 'authorization', 'cookie', 'cookies', 'password', 'private', 'secret',
                 'session', 'sessionid', 'token', 'mstoken', 'abogus', 'verifyfp', 'fp', 'lid',
                 'apikey', 'accesskey', 'accesstoken', 'refreshtoken', 'loginidentifier',
                 'svwebid', 'bdticketguardclientdata', 'odintt', 'ttwid', 'csrf', 'csrftoken',
                 'xsrftoken', 'sidguard', 'passportauthstatus', 'signature',
                 'preferredverificationchannel', '登录账号', '登录密码', '店铺列表'}
_LOGIN_MESSAGES = {'未登录', '用户未登录', '请先登录', '请重新登录', '登录失效', '登录已失效',
                   '登录过期', '登录已过期', '登录状态失效', '登录状态已过期', '登录状态已失效'}


class MerchantSkillResult(SkillResult):
    # Product listings carry rich platform fields. Other skills retain the SDK's 64 KiB limit.
    max_result_bytes: ClassVar[int] = 9 * 1024 * 1024


def _is_private_key(key):
    normalized = re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', str(key).lower())
    return (normalized in _PRIVATE_KEYS or any(part in normalized for part in
            ('cookie', 'token', 'password', 'secret', 'session', 'authorization',
             'credential', 'apikey', 'accesskey', 'abogus', 'verifyfp')))


def _safe_product_data(value, secrets=(), depth=0):
    """Retain business fields while keeping local login material off the wire."""
    if depth > 60:
        raise ValueError('merchant product nesting too deep')
    if isinstance(value, dict):
        return {str(key): _safe_product_data(child, secrets, depth + 1)
                for key, child in value.items() if not _is_private_key(key)}
    if isinstance(value, list):
        return [_safe_product_data(child, secrets, depth + 1) for child in value]
    if type(value) is int and abs(value) > 9_007_199_254_740_991:
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('invalid merchant numeric field')
    if isinstance(value, str):
        if any(secret in value for secret in secrets):
            return '[REDACTED]'
        try:
            parsed = urlsplit(value)
            if (parsed.scheme in ('http', 'https') or value.startswith('//')) and parsed.netloc:
                if parsed.username or parsed.password:
                    return '[REDACTED]'
                pairs = parse_qsl(parsed.query, keep_blank_values=True)
                if any(_is_private_key(key) for key, _ in pairs):
                    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                                       urlencode([(key, val) for key, val in pairs if not _is_private_key(key)]),
                                       parsed.fragment))
        except ValueError:
            return '[REDACTED]'
    return value


def _public_url(value, *, platform_only=False):
    if not isinstance(value, str) or len(value) > 900:
        return None
    if value.startswith('//'):
        value = 'https:' + value
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or '').lower()
        if (parsed.scheme != 'https' or not host or parsed.username or parsed.password or parsed.fragment
                or (platform_only and parsed.port not in (None, 443))
                or any(key.lower() in _SENSITIVE for key, _ in parse_qsl(parsed.query, keep_blank_values=True))):
            return None
        try:
            ip_address(host)
            return None
        except ValueError:
            pass
        if host == 'localhost' or '.' not in host:
            return None
        if platform_only and not any(host == domain or host.endswith('.' + domain)
                                     for domain in ('jinritemai.com', 'douyin.com')):
            return None
        return value
    except (ValueError, TypeError):
        return None


def _project(payload, params, secrets=()):
    rows = payload.get('data')
    total = payload.get('total')
    if isinstance(total, str) and total.isascii() and total.isdecimal():
        total = int(total)
    if not isinstance(rows, list) or len(rows) > params.page_size or type(total) is not int or total < 0:
        raise ValueError('invalid merchant page')
    items, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('invalid merchant product')
        product_id = row.get('product_id')
        if type(product_id) is int:
            product_id = str(product_id)
        if not isinstance(product_id, str) or not re.fullmatch(r'[0-9]{1,32}', product_id) or product_id in seen:
            raise ValueError('invalid merchant product id')
        seen.add(product_id)
        safe_row = _safe_product_data(row, secrets) if params.include_raw else row
        name = safe_row.get('name')
        item = {'product_id': product_id, 'name': name[:256] if isinstance(name, str) else '',
                'image_url': _public_url(safe_row.get('img')),
                'product_url': _public_url(safe_row.get('product_url'), platform_only=True)}
        if params.include_raw:
            item['platform_data'] = safe_row
        items.append(item)
    return {'state': params.state, 'page': params.page, 'page_size': params.page_size,
            'total': total, 'items': items}


async def _run(host, task, params):
    if task.result_delivery != 'operations':
        raise SkillExecutionError('OPERATIONS_DELIVERY_REQUIRED', '运营中心结果通道尚不可用')
    if len(task.local_shops) != 1:
        raise SkillExecutionError('SKILL_INPUT_INVALID', '请选择一个本机店铺')
    shop = task.local_shops[0]
    if shop.platform != 'douyin' or not shop.platform_shop_id:
        raise SkillExecutionError('SKILL_INPUT_INVALID', '本机店铺映射无效')
    try:
        session = await host.read_session(shop.local_shop_id, shop.platform_shop_id)
    except Exception as error:
        code = getattr(error, 'code', 'RPA_SESSION_UNAVAILABLE')
        if not isinstance(code, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{2,63}', code):
            code = 'RPA_SESSION_UNAVAILABLE'
        raise SkillExecutionError(code, '设备没有可用的本机店铺会话') from None
    try:
        http_status, payload = await host.read_merchant_product_page(
            session, state=params.state, page=params.page, page_size=params.page_size)
    except Exception:
        raise SkillExecutionError('PLATFORM_REQUEST_FAILED', '抖店商品读取未完成', retryable=True) from None
    if not isinstance(payload, dict):
        raise SkillExecutionError('PLATFORM_RESPONSE_INVALID', '抖店商品返回格式无效')
    code = payload.get('code')
    if http_status != 200 or code not in (0, '0') or type(code) not in (int, str):
        message = payload.get('message', payload.get('msg'))
        normalized = re.sub(r'[\s，。！？、:：!,.；;]+', '', message) if isinstance(message, str) and len(message) <= 120 else ''
        if http_status in (200, 401) and normalized in _LOGIN_MESSAGES:
            raise SkillExecutionError('SHOP_SESSION_EXPIRED', '店铺登录状态已失效')
        if http_status != 200:
            raise SkillExecutionError('PLATFORM_REQUEST_FAILED', '抖店商品读取未完成', retryable=True)
        raise SkillExecutionError('PLATFORM_BUSINESS_REJECTED', '抖店拒绝了商品读取')
    try:
        secrets = tuple({cookie.value.get_secret_value() for cookie in session.cookies
                         if len(cookie.value.get_secret_value()) >= 12}) if params.include_raw else ()
        data = _project(payload, params, secrets)
        result_type = MerchantSkillResult if params.include_raw else SkillResult
        return result_type(summary='抖店商品读取完成', data=data)
    except (ValueError, TypeError, RecursionError):
        raise SkillExecutionError('PLATFORM_RESPONSE_INVALID', '抖店商品返回格式无效') from None


async def execute(host, task):
    try:
        params = ProductPageInput.model_validate(task.input)
        result = await _run(host, task, params)
        return ExecutionResult(status=ExecutionStatus.SUCCESS, result={
            'kind': SKILL_ID, 'operation': params.operation,
            'platform_shop_id': task.local_shops[0].platform_shop_id, 'data': result.model_dump(mode='json')})
    except ValidationError:
        return ExecutionResult(status=ExecutionStatus.FAILED, error_code='SKILL_INPUT_INVALID', error_message='商品读取参数无效')
    except SkillExecutionError as error:
        return ExecutionResult(status=ExecutionStatus.FAILED, error_code=error.code, error_message=error.message)
