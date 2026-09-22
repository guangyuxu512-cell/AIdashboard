from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from time import monotonic
from typing import Any, Mapping
from uuid import UUID
from zoneinfo import ZoneInfo

from app.modules.sessions.auth_context import ShopSessionAuthContext, StoredSessionCookie
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.api_client import DouyinApiClient
from app.platforms.douyin.endpoints import COMPASS_CORE_INDEX_V3_ENDPOINT
from app.platforms.exceptions import PlatformRequestFailedError, PlatformResponseInvalidError


CORE_INDEX_SELECTED_FIELDS = (
    "income_amt",
    "pay_amt",
    "settlement_amt_pay_time",
    "pay_cnt",
    "product_show_ucnt",
    "product_click_ucnt",
    "per_usr_pay_amt",
    "pay_ucnt",
    "rfndsuc_amt",
    "rfndsuc_amt_pay_time",
    "refund_amt_rate",
    "refund_amt",
    "refund_order_cnt",
    "refund_order_cnt_pay_time",
    "product_show_click_ucnt_ratio",
    "product_click_pay_ucnt_ratio",
)
SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")


class DouyinOperatingDataBusinessError(PlatformRequestFailedError):
    """The platform returned a parsed, non-success business response."""

    code = "DOUYIN_OPERATING_DATA_REJECTED"
    message = "抖店经营数据请求未被平台接受"


@dataclass(frozen=True)
class CompassDailyMetrics:
    """Fixed values from the verified Compass core-index response path.

    Monetary fields remain integer cents at the transport boundary.  The
    derived Decimal properties are presentation-safe conversions, not a new
    accounting calculation.
    """

    income_amt_cents: int | None
    pay_cnt: int | None
    pay_amt_cents: int | None
    rfndsuc_amt_pay_time_cents: int | None
    settlement_amt_pay_time_cents: int | None

    @property
    def income_amt_yuan(self) -> Decimal | None:
        return _cents_to_yuan(self.income_amt_cents)

    @property
    def pay_amt_yuan(self) -> Decimal | None:
        return _cents_to_yuan(self.pay_amt_cents)

    @property
    def rfndsuc_amt_pay_time_yuan(self) -> Decimal | None:
        return _cents_to_yuan(self.rfndsuc_amt_pay_time_cents)

    @property
    def settlement_amt_pay_time_yuan(self) -> Decimal | None:
        return _cents_to_yuan(self.settlement_amt_pay_time_cents)


@dataclass(frozen=True)
class CompassDailyRead:
    shop_id: UUID
    statistic_date: date
    metrics: CompassDailyMetrics
    cookie_updates: tuple[StoredSessionCookie, ...]
    signature_duration_ms: int | None
    platform_duration_ms: int
    parse_duration_ms: int


class DouyinOperatingDataConnector:
    """Verified read-only Compass core-index request owned by Douyin."""

    def __init__(self, *, api_client: DouyinApiClient | None = None) -> None:
        self.api_client = api_client or DouyinApiClient()

    def fetch_daily_metrics(
        self,
        shop_id: UUID,
        auth_context: ShopSessionAuthContext,
        statistic_date: date,
        *,
        request_lid: str | None = None,
    ) -> CompassDailyRead:
        if auth_context.platform is not ShopPlatform.DOUYIN:
            raise PlatformRequestFailedError("Connector 与 Session 平台不匹配")

        response = self.api_client.request_json(
            COMPASS_CORE_INDEX_V3_ENDPOINT,
            auth_context,
            query=build_core_index_query(statistic_date, request_lid=request_lid),
        )
        parse_started_at = monotonic()
        metrics = parse_core_index_metrics(response.payload)
        return CompassDailyRead(
            shop_id=shop_id,
            statistic_date=statistic_date,
            metrics=metrics,
            cookie_updates=response.cookie_updates,
            signature_duration_ms=response.signature_duration_ms,
            platform_duration_ms=response.platform_duration_ms,
            parse_duration_ms=round((monotonic() - parse_started_at) * 1000),
        )


def build_core_index_query(
    statistic_date: date,
    *,
    request_lid: str | None = None,
) -> dict[str, str]:
    """Build only the verified business query, before `a_bogus` injection.

    `_lid` is intentionally caller-supplied.  The captured request proves it
    is per-request context but does not establish a server-side generation
    algorithm, so this module never persists or invents a browser value.
    """

    day = statistic_date.strftime("%Y/%m/%d")
    query = {
        "begin_date": f"{day} 00:00:00",
        "end_date": f"{day} 00:00:00",
        "date_type": "20",
        "activity_id": "",
        "index_selected": ",".join(CORE_INDEX_SELECTED_FIELDS),
        "operate_type": "0",
    }
    if request_lid is not None:
        normalized_lid = request_lid.strip()
        if normalized_lid:
            query["_lid"] = normalized_lid
    return query


def previous_completed_shanghai_date(reference_at: datetime | None = None) -> date:
    """Return the prior calendar day in the business reporting timezone."""

    if reference_at is None:
        local_now = datetime.now(SHANGHAI_TIMEZONE)
    else:
        if reference_at.tzinfo is None:
            raise ValueError("reference_at must include timezone information")
        local_now = reference_at.astimezone(SHANGHAI_TIMEZONE)
    return local_now.date() - timedelta(days=1)


def parse_core_index_metrics(payload: Mapping[str, Any]) -> CompassDailyMetrics:
    platform_status = payload.get("st")
    if platform_status not in {0, "0"}:
        raise DouyinOperatingDataBusinessError(
            details={"platform_code": _safe_scalar(platform_status)},
        )

    card = _core_index_card(payload)
    return CompassDailyMetrics(
        income_amt_cents=_read_integer_metric(card, "income_amt"),
        pay_cnt=_read_integer_metric(card, "pay_cnt"),
        pay_amt_cents=_read_integer_metric(card, "pay_amt"),
        rfndsuc_amt_pay_time_cents=_read_integer_metric(
            card,
            "rfndsuc_amt_pay_time",
        ),
        settlement_amt_pay_time_cents=_read_integer_metric(
            card,
            "settlement_amt_pay_time",
        ),
    )


def _core_index_card(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise PlatformResponseInvalidError(
            details={"failure_stage": "core_index_parse"},
        )
    module_data = data.get("module_data")
    if not isinstance(module_data, Mapping):
        raise PlatformResponseInvalidError(
            details={"failure_stage": "core_index_parse"},
        )
    homepage = module_data.get("homepage_core_index")
    if not isinstance(homepage, Mapping):
        raise PlatformResponseInvalidError(
            details={"failure_stage": "core_index_parse"},
        )
    card = homepage.get("compass_general_multi_index_card_value")
    if not isinstance(card, Mapping):
        raise PlatformResponseInvalidError(
            details={"failure_stage": "core_index_parse"},
        )
    rows = card.get("data")
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], Mapping):
        raise PlatformResponseInvalidError(
            details={"failure_stage": "core_index_parse"},
        )
    return rows[0]


def _read_integer_metric(card: Mapping[str, Any], field: str) -> int | None:
    metric = card.get(field)
    if not isinstance(metric, Mapping):
        raise PlatformResponseInvalidError(
            details={"failure_stage": "core_index_parse", "metric": field},
        )
    index_value = metric.get("index_value")
    if not isinstance(index_value, Mapping):
        raise PlatformResponseInvalidError(
            details={"failure_stage": "core_index_parse", "metric": field},
        )
    value_container = index_value.get("value")
    if not isinstance(value_container, Mapping) or "value" not in value_container:
        raise PlatformResponseInvalidError(
            details={"failure_stage": "core_index_parse", "metric": field},
        )
    return _to_optional_integer(value_container["value"], field)


def _to_optional_integer(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise PlatformResponseInvalidError(
            details={"failure_stage": "core_index_parse", "metric": field},
        )
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.lstrip("-").isdigit():
        return int(value)
    raise PlatformResponseInvalidError(
        details={"failure_stage": "core_index_parse", "metric": field},
    )


def _cents_to_yuan(value: int | None) -> Decimal | None:
    return None if value is None else Decimal(value) / Decimal("100")


def _safe_scalar(value: Any) -> str:
    if isinstance(value, (str, int, float, bool)):
        return str(value)[:64]
    return "unknown"
