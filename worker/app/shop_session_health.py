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

from app.rpa_session_bridge import LocalShop, RpaBridgeError


# At most one store is checked per inventory cycle. Successful checks are
# reused for 30 minutes; start revalidation early enough to avoid an expiry
# gap while the inventory loop visits the other shops.
_CONFIRMED_INTERVAL = 15 * 60
_UNKNOWN_INTERVAL = 5 * 60
_UNKNOWN_SHOP_INTERVAL = 30
_VALID_AGE = timedelta(minutes=30)
_MAX_BYTES = 256 * 1024
_REFRESH_INTERVAL = 30 * 60
_MAX_REFRESH_ATTEMPTS = 3
_EXHAUSTED_REFRESH_INTERVAL = 6 * 60 * 60
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


class ShopSessionHealth:
    def __init__(self, bridge, *, transport=None, clock=monotonic,
                 now=lambda: datetime.now(UTC)) -> None:
        self.bridge = bridge
        self.transport = transport
        self.clock = clock
        self.now = now
        self._next_check: dict[tuple[tuple[str, str, str, str | None], str], float] = {}
        self._observations: dict[tuple[tuple[str, str, str, str | None], str], SessionObservation] = {}
        self._pending: dict[tuple[str, str, str, str | None], tuple[float, set[str]]] = {}
        self._refresh_attempts: dict[tuple[str, str, str, str | None], tuple[int, float]] = {}
        self._manual_blocked: set[tuple[str, str, str, str | None]] = set()
        self._last_served: dict[tuple[str, str], int] = {}
        self._served_sequence = 0
        self._changed_snapshots: set[tuple[str, str, str, str | None]] = set()
        self._explicit_failures: set[tuple[tuple[str, str, str, str | None], str]] = set()
        self._unknown_until: dict[tuple[str, str, str], float] = {}
        self._inventory_installation = None
        self._inventory_generation = 0

    def set_installation(self, installation_id) -> bool:
        """Never transfer observations across RPA installations."""
        previous = self._inventory_installation
        self._inventory_installation = installation_id
        if previous is None or previous == installation_id:
            return False
        self._inventory_generation += 1
        self._next_check.clear()
        self._observations.clear()
        self._pending.clear()
        self._refresh_attempts.clear()
        self._manual_blocked.clear()
        self._changed_snapshots.clear()
        self._explicit_failures.clear()
        self._unknown_until.clear()
        self._last_served.clear()
        return True

    @staticmethod
    def _refresh_key(shop: LocalShop) -> tuple[str, str, str, str | None] | None:
        if shop.platform != "douyin" or not shop.platform_shop_id:
            return None
        if shop.session_stored and not shop.session_revision:
            return None  # A temporarily unavailable SQLite revision is not a missing session.
        return shop.local_shop_id, shop.platform_shop_id, shop.session_revision or "missing", shop.rpa_helper_digest

    def missing_session_due(self, shops: list[LocalShop]) -> LocalShop | None:
        for shop in shops:
            if not shop.session_stored and self._refresh_available(shop):
                return shop
        return None

    def invalid_session_due(self, shops: list[LocalShop]) -> LocalShop | None:
        """Retry a confirmed invalid snapshot without reclassifying transient errors."""
        for shop in shops:
            key = self._key(shop)
            if key is not None and self._refresh_available(shop) and any(
                (observation := self._observations.get((key, kind))) is not None
                and observation.status == 'invalid' for kind in ('merchant', 'compass')
            ):
                return shop
        return None

    def prioritize(self, shop: LocalShop, kinds: set[str]) -> bool:
        """Reserve an immediate, revision-checked probe; do not infer validity."""
        key = self._key(shop)
        requested = {kind for kind in kinds & {'merchant', 'compass'}
                     if self._unknown_until.get((shop.local_shop_id, shop.platform_shop_id, kind), 0) <= self.clock()}
        if key is None or not requested:
            return False
        self._pending[key] = (self.clock() + _UNKNOWN_INTERVAL, requested)
        return True

    def record_explicit_failure(self, shop: LocalShop, kind: str, observed_at: datetime | None = None) -> bool:
        """Record a real task's login rejection for its verified local snapshot."""
        key = self._key(shop)
        if key is None or kind not in {"merchant", "compass"}:
            return False
        self._explicit_failures.add((key, kind))
        self._unknown_until.pop((shop.local_shop_id, shop.platform_shop_id, kind), None)
        when = observed_at or self.now()
        previous = self._observations.get((key, kind))
        if previous is None or previous.status != 'invalid' or previous.checked_at < when:
            self._observations[(key, kind)] = SessionObservation("invalid", when)
        return self._refresh_available(shop)

    def _refresh_available(self, shop: LocalShop) -> bool:
        key = self._refresh_key(shop)
        if key is None or key in self._manual_blocked:
            return False
        attempts, retry_at = self._refresh_attempts.get(key, (0, 0))
        if attempts >= _MAX_REFRESH_ATTEMPTS:
            if self.clock() < retry_at + _EXHAUSTED_REFRESH_INTERVAL:
                return False
            self._refresh_attempts[key] = (0, retry_at)
        return self.clock() >= retry_at

    async def request_refresh(self, shop: LocalShop, *, expected_installation_id: str | None = None) -> bool | None:
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
            # The launch acknowledgement is not the result. An older RPA may
            # not expose outcomes yet; its other bridge operations stay usable.
            try:
                status = await self.bridge.session_refresh_status(shop.local_shop_id, shop.platform_shop_id, key[2])
            except asyncio.CancelledError:
                raise
            except Exception:
                status = None
            if status is not None:
                age = (self.now() - status.observed_at).total_seconds()
                if age >= -300:
                    age = max(0, age)
                    if status.outcome == "manual_required":
                        self._manual_blocked.add(key)
                        return False
                    if status.outcome == "saved" and age <= 24 * 60 * 60:
                        return False  # The next inventory cycle must observe the new revision.
                    delay = _REFRESH_INTERVAL if status.outcome == "retryable" else 60
                    if status.outcome in ("busy", "retryable") and age < delay:
                        self._refresh_attempts[key] = (attempts, self.clock() + delay - age)
                        return False
            if expected_installation_id is None:
                accepted = await self.bridge.request_session_refresh(shop.local_shop_id, shop.platform_shop_id, key[2], require_compass)
            else:
                accepted = await self.bridge.request_session_refresh(shop.local_shop_id, shop.platform_shop_id, key[2],
                    require_compass, expected_installation_id=expected_installation_id)
            if accepted:
                self._refresh_attempts[key] = (attempts + 1, self.clock() + _UNKNOWN_INTERVAL)
                return True
            # A malformed or missing acknowledgement does not prove that the
            # local RPA failed to start the asynchronous refresh.
            self._refresh_attempts[key] = (attempts + 1, self.clock() + _UNKNOWN_INTERVAL)
            return None
        except asyncio.CancelledError:
            raise
        except RpaBridgeError as error:
            if error.code in {'RPA_HELPER_UNTRUSTED', 'RPA_NOT_READY', 'RPA_IDENTITY_MISMATCH',
                              'RPA_SHOP_IDENTITY_MISMATCH', 'RPA_SESSION_UNAVAILABLE', 'INVALID_REQUEST'}:
                return False  # Trusted bridge rejected before launching RPA.
            self._refresh_attempts[key] = (attempts + 1, self.clock() + _UNKNOWN_INTERVAL)
            return None
        except Exception:
            self._refresh_attempts[key] = (attempts + 1, self.clock() + _UNKNOWN_INTERVAL)
            return None  # The RPA may have started before the bridge failed.

    @staticmethod
    def _key(shop: LocalShop) -> tuple[str, str, str, str | None] | None:
        if (shop.platform != "douyin" or not shop.session_stored or not shop.platform_shop_id
                or not shop.session_revision):
            return None
        return shop.local_shop_id, shop.platform_shop_id, shop.session_revision, shop.rpa_helper_digest

    def due(self, shops: list[LocalShop], *, excluded_platform_ids: frozenset[str] = frozenset()) -> LocalShop | None:
        keys = {key for shop in shops if (key := self._key(shop)) is not None}
        refresh_keys = {key for shop in shops if (key := self._refresh_key(shop)) is not None}
        # A removed or replaced snapshot cannot keep its former status.
        self._next_check = {key: value for key, value in self._next_check.items() if key[0] in keys}
        self._observations = {key: value for key, value in self._observations.items() if key[0] in keys}
        self._explicit_failures = {key for key in self._explicit_failures if key[0] in keys}
        self._pending = {key: value for key, value in self._pending.items() if key in keys}
        self._changed_snapshots.intersection_update(keys)
        self._refresh_attempts = {key: value for key, value in self._refresh_attempts.items() if key in refresh_keys}
        self._manual_blocked.intersection_update(refresh_keys)
        identities = {(shop.local_shop_id, shop.platform_shop_id) for shop in shops if shop.platform_shop_id}
        self._last_served = {key: value for key, value in self._last_served.items() if key in identities}
        self._unknown_until = {key: value for key, value in self._unknown_until.items() if key[:2] in identities}
        now = self.clock()
        candidates = []
        for shop in shops:
            if shop.platform_shop_id in excluded_platform_ids:
                continue
            key = self._key(shop)
            if key is not None and (key not in self._pending or self._pending[key][0] <= now):
                due = {kind for kind in ("merchant", "compass")
                       if max(self._next_check.get((key, kind), 0),
                              self._unknown_until.get((shop.local_shop_id, shop.platform_shop_id, kind), 0)) <= now}
                if not due:
                    continue
                candidates.append((min(self._next_check.get((key, kind), 0) for kind in due),
                                   self._last_served.get((shop.local_shop_id, shop.platform_shop_id), 0),
                                   shop, key, due))
        if candidates:
            # Unchecked/longest-waiting shops take priority over retries, so a
            # handful of unavailable shops cannot starve the rest of a fleet.
            _, _, shop, key, due = min(candidates, key=lambda candidate: (candidate[0], candidate[1]))
            self._served_sequence += 1
            self._last_served[(shop.local_shop_id, shop.platform_shop_id)] = self._served_sequence
            for kind in due:
                self._next_check[(key, kind)] = now + _UNKNOWN_INTERVAL
            self._pending[key] = (now + _UNKNOWN_INTERVAL, due)
            return shop
        return None

    def has_due(self, shops: list[LocalShop], *, excluded_platform_ids: frozenset[str] = frozenset()) -> bool:
        """Check for other due shops without reserving or changing a probe."""
        now = self.clock()
        for shop in shops:
            if shop.platform_shop_id in excluded_platform_ids:
                continue
            key = self._key(shop)
            if key is not None and (key not in self._pending or self._pending[key][0] <= now):
                if any(max(self._next_check.get((key, kind), 0),
                           self._unknown_until.get((shop.local_shop_id, shop.platform_shop_id, kind), 0)) <= now
                       for kind in ('merchant', 'compass')):
                    return True
        return False

    def unknown_retry_delay(self, shops: list[LocalShop], *, excluded_platform_ids: frozenset[str] = frozenset()) -> float | None:
        now = self.clock()
        identities = {(shop.local_shop_id, shop.platform_shop_id) for shop in shops
                      if shop.platform_shop_id and shop.platform_shop_id not in excluded_platform_ids}
        future = [until - now for key, until in self._unknown_until.items()
                  if key[:2] in identities and until > now]
        return max(0.01, min(future)) if future else None

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
        generation = self._inventory_generation
        reserved = self._pending.pop(key, None)
        kinds = reserved[1] if reserved else {"merchant", "compass"}
        results: dict[str, Literal["valid", "invalid"] | None] = {kind: None for kind in kinds}
        cancelled = False
        probed = False
        try:
            before = await self.bridge.session_revision(shop.local_shop_id, shop.platform_shop_id)
            if generation != self._inventory_generation:
                return False
            if before is None:
                self._changed_snapshots.add(key)
                return False  # Unreadable is not proof that the snapshot changed.
            if before != shop.session_revision:
                self._changed_snapshots.add(key)
                for kind in ("merchant", "compass"):
                    self._observations.pop((key, kind), None)
                return False
            session = await self.bridge.read_session(shop.local_shop_id, shop.platform_shop_id)
            probed = True
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
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        # One unavailable service must not hide the other service's status.
                        pass
            after = await self.bridge.session_revision(shop.local_shop_id, shop.platform_shop_id)
            if generation != self._inventory_generation:
                return False
            if after is None:
                self._changed_snapshots.add(key)
                results = {kind: None for kind in kinds}
                probed = False
            elif after != shop.session_revision:
                self._changed_snapshots.add(key)
                for kind in ("merchant", "compass"):
                    self._observations.pop((key, kind), None)
                results = {kind: None for kind in kinds}
                probed = False
        except asyncio.CancelledError:
            cancelled = True
            raise
        except RpaBridgeError as error:
            if (generation == self._inventory_generation
                    and error.code in {'RPA_SHOP_IDENTITY_MISMATCH', 'RPA_NOT_READY', 'RPA_HELPER_UNTRUSTED'}):
                self._changed_snapshots.add(key)
            return False
        except Exception:
            # Network, risk control, parsing and bridge failures are not proof
            # that the login expired. Never log a platform response or Session.
            return False
        finally:
            if generation == self._inventory_generation:
                for kind, result in results.items():
                    self._next_check[(key, kind)] = (0 if cancelled else self.clock() + (
                        _CONFIRMED_INTERVAL if result else _UNKNOWN_INTERVAL
                    ))
                    if probed and not cancelled:
                        identity = (shop.local_shop_id, shop.platform_shop_id, kind)
                        if result is None:
                            self._unknown_until[identity] = self.clock() + _UNKNOWN_SHOP_INTERVAL
                        else:
                            self._unknown_until.pop(identity, None)
        for kind, result in results.items():
            if result is not None and not (result == 'valid' and (key, kind) in self._explicit_failures):
                self._observations[(key, kind)] = SessionObservation(result, self.now())
        confirmed_invalid = (any(result == "invalid" for result in results.values())
                             or any((key, kind) in self._explicit_failures for kind in kinds))
        return confirmed_invalid and self._refresh_available(shop)

    def take_snapshot_changed(self, shop: LocalShop) -> bool:
        key = self._key(shop)
        if key is not None and key in self._changed_snapshots:
            self._changed_snapshots.remove(key)
            return True
        return False


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
    # A business rejection or identity mismatch is not proof of expiry.
    return IdentityProbe(None)


def _explicit_login_failure(payload: dict) -> bool:
    for name in ("message", "msg", "error_msg", "error_message"):
        value = payload.get(name)
        if isinstance(value, str) and len(value) <= 120:
            normalized = re.sub(r"[\s，。！？、:：!,.；;]+", "", value).lower()
            if normalized in _LOGIN_MESSAGES:
                return True
    return False
