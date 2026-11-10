"""Restricted host services exposed to verified, signed capability modules."""
from __future__ import annotations

import json
import logging
import re
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

import httpx

from app.rpa_session_bridge import LocalSession, RpaLocalBridge


_MAX_PLATFORM_BYTES = 3 * 1024 * 1024


class _NoQueryHttpxLogs(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.msg == 'HTTP Request: %s %s "%s %d %s"' and isinstance(record.args, tuple) and len(record.args) == 5:
            args = list(record.args)
            args[1] = str(args[1]).split("?", 1)[0]
            record.args = tuple(args)
        return True


_httpx_logger = logging.getLogger("httpx")
if not any(isinstance(value, _NoQueryHttpxLogs) for value in _httpx_logger.filters):
    _httpx_logger.addFilter(_NoQueryHttpxLogs())


class CapabilityHost:
    def __init__(self, device_id: UUID, client, rpa: RpaLocalBridge | None, *, transport=None):
        self.device_id = device_id
        self._client = client
        self._rpa = rpa
        self._transport = transport

    async def read_session(self, local_shop_id: str, platform_shop_id: str) -> LocalSession:
        if self._rpa is None:
            from app.rpa_session_bridge import RpaBridgeError
            raise RpaBridgeError("RPA_NOT_READY")
        return await self._rpa.read_session(local_shop_id, platform_shop_id)

    @staticmethod
    def cookie_header(session: LocalSession) -> str:
        cookies = httpx.Cookies()
        for cookie in session.cookies:
            cookies.set(cookie.name, cookie.value.get_secret_value(), domain=cookie.domain, path=cookie.path)
        request = httpx.Request("POST", "https://fxg.jinritemai.com/product/tproduct/getSchema", cookies=cookies)
        header = request.headers.get("cookie", "")
        if not header:
            raise ValueError("session unavailable")
        return header

    async def sign_precheck(self, task_id: UUID, cookie: str, user_agent: str) -> dict[str, str]:
        return await self._client.sign_precheck(task_id, cookie=cookie, user_agent=user_agent)

    async def post_schema(self, signed: dict[str, str], cookie: str, user_agent: str,
                          expected: dict[str, str]) -> tuple[int, object]:
        try:
            parsed = urlsplit(signed["url"])
            query = parse_qsl(parsed.query, keep_blank_values=True)
            names = [key for key, _ in query]
            if (parsed.scheme != "https" or parsed.hostname != "fxg.jinritemai.com" or parsed.port is not None
                    or parsed.username is not None or parsed.password is not None
                    or parsed.path != "/product/tproduct/getSchema" or parsed.fragment
                    or len(names) != len(set(names))
                    or set(names) - {"appid", "_bid", "_lid", "verifyFp", "fp", "msToken", "a_bogus"}
                    or "a_bogus" not in names):
                raise ValueError("invalid signer target")
            body = signed["body"].encode("utf-8")
            if len(body) > 16 * 1024:
                raise ValueError("request too large")
            payload = json.loads(body)
            if (payload["context"]["category_id"] != expected["category_id"]
                    or payload["model"]["title"]["value"] != expected["title"]):
                raise ValueError("request identity mismatch")
            headers = {"accept": "application/json, text/plain, */*", "user-agent": user_agent,
                       "accept-language": "zh-CN,zh;q=0.9", "cache-control": "no-cache", "pragma": "no-cache",
                       "referer": "https://fxg.jinritemai.com/ffa/g/create",
                       "origin": "https://fxg.jinritemai.com", "cookie": cookie,
                       "content-type": "application/json;charset=UTF-8", "x-tt-from-end": "PC",
                       "x-tt-from-appid": "ffa-goods", "x-tt-from-page": "https://fxg.jinritemai.com/ffa/g/create",
                       "x-tt-from-version": "1.0.1.3675", "sec-ch-ua-mobile": "?0",
                       "sec-ch-ua-platform": '"Windows"', "sec-fetch-dest": "empty",
                       "sec-fetch-mode": "cors", "sec-fetch-site": "same-origin"}
            chrome = re.search(r"Chrome/(\d+)", user_agent)
            if chrome:
                major = chrome.group(1)
                headers["sec-ch-ua"] = f'"Chromium";v="{major}", "Google Chrome";v="{major}", "Not/A)Brand";v="99"'
            for part in cookie.split(";"):
                key, separator, value = part.strip().partition("=")
                if key == "csrf_session_id" and separator:
                    headers["x-secsdk-csrf-token"] = value
            async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False,
                                         transport=self._transport) as client:
                async with client.stream("POST", signed["url"], headers=headers, content=body) as response:
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > _MAX_PLATFORM_BYTES:
                            raise ValueError("platform response too large")
                    try:
                        decoded = json.loads(content)
                    except (ValueError, UnicodeError):
                        decoded = None
                    return response.status_code, decoded
        except (KeyError, TypeError, ValueError, httpx.HTTPError, OSError):
            # Do not propagate a signed URL, Cookie or platform response to logs.
            raise RuntimeError("PRECHECK_TRANSPORT_FAILED") from None
