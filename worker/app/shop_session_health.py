"""Verify locally saved merchant and Compass sessions without exporting them."""
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
        self._next_check: dict[tuple[tuple[str, str, str], str], float] = {}
        self._observations: dict[tuple[tuple[str, str, str], str], SessionObservation] = {}
        self._pending: dict[tuple[str, str, str], tuple[float, set[str]]] = {}

    @staticmethod
    def _key(shop: LocalShop) -> tuple[str, str, str] | None:
        if (shop.platform != "douyin" or not shop.session_stored or not shop.platform_shop_id
                or not shop.session_revision):
            return None
        return shop.local_shop_id, shop.platform_shop_id, shop.session_revision

    def due(self, shops: list[LocalShop]) -> LocalShop | None:
        keys = {key for shop in shops if (key := self._key(shop)) is not None}
        # A removed or replaced snapshot cannot keep its former status.
        self._next_check = {key: value for key, value in self._next_check.items() if key[0] in keys}
        self._observations = {key: value for key, value in self._observations.items() if key[0] in keys}
        self._pending = {key: value for key, value in self._pending.items() if key in keys}
        now = self.clock()
        candidates = []
        for shop in shops:
            key = self._key(shop)
            if key is not None and (key not in self._pending or self._pending[key][0] <= now):
                due = {kind for kind in ("merchant", "compass")
                       if self._next_check.get((key, kind), 0) <= now}
                if not due:
                    continue
                candidates.append((min(self._next_check.get((key, kind), 0) for kind in due), shop, key, due))
        if candidates:
            # Unchecked/longest-waiting shops take priority over retries, so a
            # handful of unavailable shops cannot starve the rest of a fleet.
            _, shop, key, due = min(candidates, key=lambda candidate: candidate[0])
            for kind in due:
                self._next_check[(key, kind)] = now + _UNKNOWN_INTERVAL
            self._pending[key] = (now + _UNKNOWN_INTERVAL, due)
            return shop
        return None

    def report(self, shop: LocalShop) -> dict[str, str | None]:
        key = self._key(shop)
        report: dict[str, str | None] = {}
        for kind, status_field, time_field in (
            ("merchant", "sessionStatus", "sessionCheckedAt"),
            ("compass", "compassSessionStatus", "compassSessionCheckedAt"),
        ):
            observation = self._observations.get((key, kind)) if key else None
            if observation is None or (
                observation.status == "valid" and self.now() - observation.checked_at > _VALID_AGE
            ):
                report.update({status_field: None, time_field: None})
            else:
                report.update({status_field: observation.status, time_field: observation.checked_at.isoformat()})
        return report

    async def check(self, shop: LocalShop) -> None:
        key = self._key(shop)
        if key is None:
            return
        reserved = self._pending.pop(key, None)
        kinds = reserved[1] if reserved else {"merchant", "compass"}
        results: dict[str, Literal["valid", "invalid"] | None] = {kind: None for kind in kinds}
        try:
            if await self.bridge.session_revision(shop.local_shop_id, shop.platform_shop_id) != shop.session_revision:
                for kind in ("merchant", "compass"):
                    self._observations.pop((key, kind), None)
                return
            session = await self.bridge.read_session(shop.local_shop_id, shop.platform_shop_id)
            cookies = httpx.Cookies()
            for cookie in session.cookies:
                cookies.set(cookie.name, cookie.value.get_secret_value(), domain=cookie.domain, path=cookie.path)
            async with httpx.AsyncClient(timeout=8, follow_redirects=False,
                                         trust_env=False, transport=self.transport) as client:
                for kind in sorted(kinds):
                    try:
                        results[kind] = await _check_identity(
                            client, cookies, session.user_agent, shop.platform_shop_id, kind,
                        )
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        # One unavailable service must not hide the other service's status.
                        pass
            if await self.bridge.session_revision(shop.local_shop_id, shop.platform_shop_id) != shop.session_revision:
                for kind in ("merchant", "compass"):
                    self._observations.pop((key, kind), None)
                results = {kind: None for kind in kinds}
        except asyncio.CancelledError:
            raise
        except Exception:
            # Network, risk control, parsing and bridge failures are not proof
            # that the login expired. Never log a platform response or Session.
            return
        finally:
            for kind, result in results.items():
                self._next_check[(key, kind)] = self.clock() + (
                    _CONFIRMED_INTERVAL if result else _UNKNOWN_INTERVAL
                )
        for kind, result in results.items():
            if result is not None:
                self._observations[(key, kind)] = SessionObservation(result, self.now())


async def _check_identity(client: httpx.AsyncClient, cookies: httpx.Cookies, user_agent: str,
                          expected_shop_id: str, kind: str) -> Literal["valid", "invalid"] | None:
    if kind == "merchant":
        url = "https://fxg.jinritemai.com/common/index/index"
        referer = "https://fxg.jinritemai.com/ffa/g/create"
        code_field, identity_field = "code", "id"
    else:
        # The same read-only identity endpoint used by RPA's session capture.
        url = "https://compass.jinritemai.com/compass_api/shop/mall/common/shop_info_v2"
        referer = "https://compass.jinritemai.com/shop"
        code_field, identity_field = "st", "shop_id"
    headers = {"accept": "application/json, text/plain, */*", "referer": referer, "user-agent": user_agent}
    async with client.stream("GET", url, headers=headers, cookies=cookies) as response:
        status = response.status_code
        raw = bytearray()
        async for chunk in response.aiter_bytes():
            raw.extend(chunk)
            if len(raw) > _MAX_BYTES:
                return None
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    identity = data.get(identity_field) if isinstance(data, dict) else None
    code = payload.get(code_field)
    if (status == 200 and type(code) is int and code == 0
            and identity is not None and not isinstance(identity, bool) and str(identity) == expected_shop_id):
        return "valid"
    if status in (200, 401) and code != 0 and _explicit_login_failure(payload):
        return "invalid"
    return None


def _explicit_login_failure(payload: dict) -> bool:
    for name in ("message", "msg", "error_msg", "error_message"):
        value = payload.get(name)
        if isinstance(value, str) and len(value) <= 120:
            normalized = re.sub(r"[\s，。！？、:：!,.；;]+", "", value).lower()
            if normalized in _LOGIN_MESSAGES:
                return True
    return False
