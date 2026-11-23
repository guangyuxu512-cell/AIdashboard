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
_REFRESH_INTERVAL = 30 * 60
_MAX_REFRESH_ATTEMPTS = 3
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


@dataclass(frozen=True, slots=True)
class IdentityProbe:
    status: Literal["valid", "invalid"] | None
    can_prepare_compass: bool = False


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
        self._refresh_attempts: dict[tuple[str, str, str], tuple[int, float]] = {}

    @staticmethod
    def _refresh_key(shop: LocalShop) -> tuple[str, str, str] | None:
        if shop.platform != "douyin" or not shop.platform_shop_id:
            return None
        if shop.session_stored and not shop.session_revision:
            return None  # A temporarily unavailable SQLite revision is not a missing session.
        return shop.local_shop_id, shop.platform_shop_id, shop.session_revision or "missing"

    def missing_session_due(self, shops: list[LocalShop]) -> LocalShop | None:
        for shop in shops:
            if not shop.session_stored and self._refresh_available(shop):
                return shop
        return None

    def _refresh_available(self, shop: LocalShop) -> bool:
        key = self._refresh_key(shop)
        if key is None:
            return False
        attempts, retry_at = self._refresh_attempts.get(key, (0, 0))
        report = self.report(shop)
        # An unverified Compass snapshot is not proof of expiry. Give it one
        # background preparation attempt; reserve retries for missing or
        # explicitly invalid sessions.
        unverified = (shop.session_stored and shop.compass_session_verified is False
                      and report["sessionStatus"] == "valid"
                      and report["compassSessionStatus"] is None)
        limit = 1 if unverified else _MAX_REFRESH_ATTEMPTS
        return attempts < limit and self.clock() >= retry_at

    async def request_refresh(self, shop: LocalShop) -> bool:
        key = self._refresh_key(shop)
        if key is None or not self._refresh_available(shop):
            return False
        attempts, _ = self._refresh_attempts.get(key, (0, 0))
        # Reserve the slot before awaiting the bridge.  An old or unavailable
        # RPA must not exhaust this snapshot's attempts before it is updated.
        self._refresh_attempts[key] = (attempts, self.clock() + _UNKNOWN_INTERVAL)
        # Missing or explicitly expired merchant sessions must be recoverable
        # even if this shop cannot establish Compass. A Compass-only refresh
        # must not replace the still-usable merchant snapshot on failure.
        require_compass = shop.session_stored and self.report(shop)["sessionStatus"] != "invalid"
        try:
            accepted = await self.bridge.request_session_refresh(shop.local_shop_id, shop.platform_shop_id, key[2], require_compass)
            if accepted:
                self._refresh_attempts[key] = (attempts + 1, self.clock() + _REFRESH_INTERVAL)
            return accepted
        except asyncio.CancelledError:
            raise
        except Exception:
            return False

    @staticmethod
    def _key(shop: LocalShop) -> tuple[str, str, str] | None:
        if (shop.platform != "douyin" or not shop.session_stored or not shop.platform_shop_id
                or not shop.session_revision):
            return None
        return shop.local_shop_id, shop.platform_shop_id, shop.session_revision

    def due(self, shops: list[LocalShop]) -> LocalShop | None:
        keys = {key for shop in shops if (key := self._key(shop)) is not None}
        refresh_keys = {key for shop in shops if (key := self._refresh_key(shop)) is not None}
        # A removed or replaced snapshot cannot keep its former status.
        self._next_check = {key: value for key, value in self._next_check.items() if key[0] in keys}
        self._observations = {key: value for key, value in self._observations.items() if key[0] in keys}
        self._pending = {key: value for key, value in self._pending.items() if key in keys}
        self._refresh_attempts = {key: value for key, value in self._refresh_attempts.items() if key in refresh_keys}
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

    async def check(self, shop: LocalShop) -> bool:
        key = self._key(shop)
        if key is None:
            return False
        reserved = self._pending.pop(key, None)
        kinds = reserved[1] if reserved else {"merchant", "compass"}
        results: dict[str, Literal["valid", "invalid"] | None] = {kind: None for kind in kinds}
        compass_reachable = False
        try:
            if await self.bridge.session_revision(shop.local_shop_id, shop.platform_shop_id) != shop.session_revision:
                for kind in ("merchant", "compass"):
                    self._observations.pop((key, kind), None)
                return False
            session = await self.bridge.read_session(shop.local_shop_id, shop.platform_shop_id)
            cookies = httpx.Cookies()
            for cookie in session.cookies:
                cookies.set(cookie.name, cookie.value.get_secret_value(), domain=cookie.domain, path=cookie.path)
            async with httpx.AsyncClient(timeout=8, follow_redirects=False,
                                         trust_env=False, transport=self.transport) as client:
                for kind in sorted(kinds):
                    try:
                        probe = await _check_identity(
                            client, cookies, session.user_agent, shop.platform_shop_id, kind,
                        )
                        results[kind] = probe.status
                        if kind == "compass":
                            compass_reachable = probe.can_prepare_compass
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        # One unavailable service must not hide the other service's status.
                        pass
            if await self.bridge.session_revision(shop.local_shop_id, shop.platform_shop_id) != shop.session_revision:
                for kind in ("merchant", "compass"):
                    self._observations.pop((key, kind), None)
                results = {kind: None for kind in kinds}
                compass_reachable = False
        except asyncio.CancelledError:
            raise
        except Exception:
            # Network, risk control, parsing and bridge failures are not proof
            # that the login expired. Never log a platform response or Session.
            return False
        finally:
            for kind, result in results.items():
                self._next_check[(key, kind)] = self.clock() + (
                    _CONFIRMED_INTERVAL if result else _UNKNOWN_INTERVAL
                )
        for kind, result in results.items():
            if result is not None:
                self._observations[(key, kind)] = SessionObservation(result, self.now())
        confirmed_invalid = any(result == "invalid" for result in results.values())
        needs_initial_compass = (shop.compass_session_verified is False and compass_reachable
                                 and results.get("compass") is None
                                 and self.report(shop)["sessionStatus"] == "valid"
                                 and self.report(shop)["compassSessionStatus"] is None)
        return (confirmed_invalid or needs_initial_compass) and self._refresh_available(shop)


async def _check_identity(client: httpx.AsyncClient, cookies: httpx.Cookies, user_agent: str,
                          expected_shop_id: str, kind: str) -> IdentityProbe:
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
                return IdentityProbe(None)
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        return IdentityProbe(None)
    data = payload.get("data")
    identity = data.get(identity_field) if isinstance(data, dict) else None
    code = payload.get(code_field)
    if (status == 200 and type(code) is int and code == 0
            and identity is not None and not isinstance(identity, bool) and str(identity) == expected_shop_id):
        return IdentityProbe("valid")
    if status in (200, 401) and code != 0 and _explicit_login_failure(payload):
        return IdentityProbe("invalid")
    # An unverified snapshot may need its first Compass visit, but a failed
    # network request, non-200 response or a different shop is not that signal.
    can_prepare = (kind == "compass" and status == 200 and type(code) is int
                   and code != 0 and identity is None)
    return IdentityProbe(None, can_prepare)


def _explicit_login_failure(payload: dict) -> bool:
    for name in ("message", "msg", "error_msg", "error_message"):
        value = payload.get(name)
        if isinstance(value, str) and len(value) <= 120:
            normalized = re.sub(r"[\s，。！？、:：!,.；;]+", "", value).lower()
            if normalized in _LOGIN_MESSAGES:
                return True
    return False
