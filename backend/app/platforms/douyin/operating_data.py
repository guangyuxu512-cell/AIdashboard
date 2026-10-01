from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from time import monotonic
from typing import Any, Literal, Mapping
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

# `refund_order_cnt` is the only refund field whose page label and date
# attribution are verified for this contract: “退款订单数（退款时间）”.  The
# companion `refund_order_cnt_pay_time` stays intentionally unparsed.
RefundOrderObservationStatus = Literal[
    "available",
    "unavailable",
    "not_ready",
    "invalid",
]


class DouyinOperatingDataBusinessError(PlatformRequestFailedError):
    """The platform returned a parsed, non-success business response."""

    code = "DOUYIN_OPERATING_DATA_REJECTED"
    message = "抖店经营数据请求未被平台接受"


class DouyinOperatingDataMetricUnavailableError(PlatformResponseInvalidError):
    """A fixed Compass metric path exists but supplies no scalar value.

    This is intentionally *not* a zero-value fallback.  The observed card
    shape has a value container containing only ``unit``; until Compass
    documents a no-business semantic for that shape, the collector must keep
    the day as an explicit unknown observation rather than fabricate a daily
    fact or infer that the Shop was not operating.
    """

    code = "DOUYIN_OPERATING_DATA_METRICS_UNAVAILABLE"
    message = "抖店平台未提供可确认的经营指标值"


class DouyinOperatingDataMetricNotReadyError(PlatformResponseInvalidError):
    """Compass explicitly returned a null core metric value."""

    code = "DOUYIN_OPERATING_DATA_METRICS_NOT_READY"
    message = "抖店经营指标暂未就绪"


class DouyinOperatingDataMetricMissingError(PlatformResponseInvalidError):
    """Compass omitted a required core metric from an otherwise valid card."""

    code = "DOUYIN_OPERATING_DATA_CORE_METRIC_MISSING"
    message = "抖店经营数据响应缺少必要指标"


@dataclass(frozen=True)
class CompassDailyMetrics:
    """Persisted facts from the verified Compass core-index response path.

    Only the metrics that the Operating Dashboard currently persists and
    exposes are read here.  Compass may omit other requested card fields for
    an otherwise successful response; parsing an unimplemented field must not
    turn a valid turnover/order observation into a failed collection item.

    Monetary values remain integer cents at the transport boundary.  The
    derived Decimal property is presentation-safe conversion, not a new
    accounting calculation.
    """

    income_amt_cents: int | None
    pay_cnt: int | None
    # A refund observation is optional relative to the two core facts.  It
    # therefore carries an explicit safe status instead of making an
    # otherwise usable turnover/order response fail as a whole.  `unobserved`
    # is used only by compatibility fixtures; real parser output is one of
    # the four statuses above.
    refund_order_count: int | None = None
    refund_order_status: RefundOrderObservationStatus | Literal["unobserved"] = (
        "unobserved"
    )

    @property
    def income_amt_yuan(self) -> Decimal | None:
        return _cents_to_yuan(self.income_amt_cents)


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
        # Explicit begin/end boundaries use the Compass custom-date mode.
        "date_type": "999",
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
    refund_order_count, refund_order_status = _read_optional_integer_metric(
        card,
        "refund_order_cnt",
    )
    return CompassDailyMetrics(
        income_amt_cents=_read_integer_metric(card, "income_amt"),
        pay_cnt=_read_integer_metric(card, "pay_cnt"),
        refund_order_count=refund_order_count,
        refund_order_status=refund_order_status,
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
    if field not in card:
        raise DouyinOperatingDataMetricMissingError(
            details={"failure_stage": "core_index_parse", "metric": field},
        )
    metric = card[field]
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
    if not isinstance(value_container, Mapping):
        raise PlatformResponseInvalidError(
            details={"failure_stage": "core_index_parse", "metric": field},
        )
    if "value" not in value_container:
        if _is_unit_only_value_container(value_container):
            raise DouyinOperatingDataMetricUnavailableError(
                details={"failure_stage": "core_index_parse", "metric": field},
            )
        raise PlatformResponseInvalidError(
            details={"failure_stage": "core_index_parse", "metric": field},
        )
    if value_container["value"] is None:
        raise DouyinOperatingDataMetricNotReadyError(
            details={"failure_stage": "core_index_parse", "metric": field},
        )
    return _to_optional_integer(value_container["value"], field)


def _is_unit_only_value_container(value_container: Mapping[str, Any]) -> bool:
    """Recognize the audited Compass shape without treating it as a number.

    The check is deliberately exact.  We do not recursively search another
    branch for a same-named field, and any different missing-value structure
    remains a normal invalid-response failure until there is a separate
    platform contract for it.
    """

    return set(value_container) == {"unit"}


def _read_optional_integer_metric(
    card: Mapping[str, Any],
    field: str,
) -> tuple[int | None, RefundOrderObservationStatus]:
    """Read the frozen optional refund field without weakening core parsing.

    The platform can legitimately omit an optional card, return a null while
    the day is not ready, or change an otherwise unexpected shape.  Those
    cases are persisted as separate observation states so they never become a
    fabricated zero or a retry loop, while `income_amt` / `pay_cnt` retain
    their strict fixed-path behavior.
    """

    if field not in card:
        return None, "unavailable"
    metric = card[field]
    if not isinstance(metric, Mapping):
        return None, "invalid"
    index_value = metric.get("index_value")
    if not isinstance(index_value, Mapping):
        return None, "invalid"
    value_container = index_value.get("value")
    if not isinstance(value_container, Mapping) or "value" not in value_container:
        return None, "invalid"
    value = value_container["value"]
    if value is None:
        return None, "not_ready"
    try:
        parsed = _to_optional_integer(value, field)
    except PlatformResponseInvalidError:
        return None, "invalid"
    if parsed is None or parsed < 0:
        return None, "invalid"
    return parsed, "available"


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
