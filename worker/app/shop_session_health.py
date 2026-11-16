"""Verify a local saved merchant Session without exporting it or opening a browser."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import re
from time import monotonic
from typing import Literal

import httpx

from app.rpa_session_bridge import LocalShop


# At most one store is checked per inventory cycle. Successful checks are
# reused for 30 minutes; inconclusive checks are retried no sooner than 5.
_CONFIRMED_INTERVAL = 30 * 60
_UNKNOWN_INTERVAL = 5 * 60
_VALID_AGE = timedelta(minutes=30)
_MAX_BYTES = 256 * 1024
_LOGIN_MESSAGES = {
    "未登录", "用户未登录", "请先登录", "请重新登录", "登录失效", "登录已失效",
    "登录过期", "登录已过期", "登录状态失效", "登录状态已失效", "登录状态已过期",
    "登录失效请重新登录", "登录过期请重新登录", "登录状态已失效请重新登录",
    "登录状态已过期请重新登录", "sessionexpired", "loginrequired", "notloggedin",
}


@dataclass(frozen=True, slots=True)
class SessionObservation:
    status: Literal["valid", "invalid"]
    checked_at: datetime


class ShopSessionHealth:
    def __init__(self, bridge, *, transport=None, clock=monotonic,
                 now=lambda: datetime.now(UTC)) -> None:
        self.bridge = bridge
        self.transport = transport
        self.clock = clock
        self.now = now
        self._next_check: dict[tuple[str, str, str], float] = {}
        self._observations: dict[tuple[str, str, str], SessionObservation] = {}

    @staticmethod
    def _key(shop: LocalShop) -> tuple[str, str, str] | None:
        if (shop.platform != "douyin" or not shop.session_stored or not shop.platform_shop_id
                or not shop.session_revision):
            return None
        return shop.local_shop_id, shop.platform_shop_id, shop.session_revision

    def due(self, shops: list[LocalShop]) -> LocalShop | None:
        keys = {key for shop in shops if (key := self._key(shop)) is not None}
        # A removed or replaced snapshot cannot keep its former status.
        self._next_check = {key: value for key, value in self._next_check.items() if key in keys}
        self._observations = {key: value for key, value in self._observations.items() if key in keys}
        now = self.clock()
        for shop in shops:
            key = self._key(shop)
            if key is not None and self._next_check.get(key, 0) <= now:
                # Reserve even on cancellation, so busy Workers do not spin.
                self._next_check[key] = now + _UNKNOWN_INTERVAL
                return shop
        return None

    def report(self, shop: LocalShop) -> dict[str, str | None]:
        key = self._key(shop)
        observation = self._observations.get(key) if key else None
        if observation is None or (
            observation.status == "valid" and self.now() - observation.checked_at > _VALID_AGE
        ):
            return {"sessionStatus": None, "sessionCheckedAt": None}
        return {"sessionStatus": observation.status, "sessionCheckedAt": observation.checked_at.isoformat()}

    async def check(self, shop: LocalShop) -> None:
        key = self._key(shop)
        if key is None:
            return
        result: Literal["valid", "invalid"] | None = None
        try:
            if await self.bridge.session_revision(shop.local_shop_id, shop.platform_shop_id) != shop.session_revision:
                return
            session = await self.bridge.read_session(shop.local_shop_id, shop.platform_shop_id)
            cookies = httpx.Cookies()
            for cookie in session.cookies:
                cookies.set(cookie.name, cookie.value.get_secret_value(), domain=cookie.domain, path=cookie.path)
            headers = {
                "accept": "application/json, text/plain, */*",
                "referer": "https://fxg.jinritemai.com/ffa/g/create",
                "user-agent": session.user_agent,
            }
            async with httpx.AsyncClient(timeout=8, follow_redirects=False,
                                         trust_env=False, transport=self.transport) as client:
                async with client.stream("GET", "https://fxg.jinritemai.com/common/index/index",
                                         headers=headers, cookies=cookies) as response:
                    status = response.status_code
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw) > _MAX_BYTES:
                            return
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                return
            data = payload.get("data")
            identity = data.get("id") if isinstance(data, dict) else None
            code = payload.get("code")
            if (status == 200 and type(code) is int and code == 0
                    and identity is not None and not isinstance(identity, bool)
                    and str(identity) == shop.platform_shop_id):
                result = "valid"
            elif status in (200, 401) and code != 0 and _explicit_login_failure(payload):
                result = "invalid"
            if await self.bridge.session_revision(shop.local_shop_id, shop.platform_shop_id) != shop.session_revision:
                result = None
        except asyncio.CancelledError:
            raise
        except Exception:
            # Network, risk control, parsing and bridge failures are not proof
            # that the login expired. Never log a platform response or Session.
            return
        finally:
            self._next_check[key] = self.clock() + (
                _CONFIRMED_INTERVAL if result else _UNKNOWN_INTERVAL
            )
        if result is not None:
            self._observations[key] = SessionObservation(result, self.now())


def _explicit_login_failure(payload: dict) -> bool:
    for name in ("message", "msg", "error_msg", "error_message"):
        value = payload.get(name)
        if isinstance(value, str) and len(value) <= 120:
            normalized = re.sub(r"[\s，。！？、:：!,.；;]+", "", value).lower()
            if normalized in _LOGIN_MESSAGES:
                return True
    return False
