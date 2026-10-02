from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Iterable, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.modules.access.contracts import ActorContext
from app.modules.access.module_access import ModuleCode
from app.modules.access.service import ActorContextService, ModuleAccessService
from app.modules.operating_dashboard.enums import (
    OperatingCollectionItemStatus,
    OperatingCollectionJobKind,
    OperatingCollectionJobStatus,
)
from app.modules.operating_dashboard.exceptions import (
    OperatingDashboardCollectionNotFoundError,
    OperatingDashboardCollectionRetryUnavailableError,
    OperatingDashboardCollectionUnavailableError,
    OperatingDashboardInvalidRequestError,
    OperatingDashboardShopNotAvailableError,
)
from app.modules.operating_dashboard.models import (
    OperatingDataCollectionItem,
    OperatingDataCollectionJob,
    ShopOperatingDailyMetric,
)
from app.modules.operating_dashboard.repository import (
    CollectionClaim,
    CollectionItemState,
    DashboardShop,
    OperatingDashboardRepository,
)
from app.modules.operating_dashboard.schemas import (
    OperatingDashboardComparisonRead,
    OperatingDashboardCoverageMissingRead,
    OperatingDashboardCoverageRead,
    OperatingDashboardDateRangeRead,
    OperatingDashboardRead,
    OperatingDashboardShopOptionRead,
    OperatingDashboardSummaryRead,
    OperatingDashboardTablePageRead,
    OperatingDashboardTableRowRead,
    OperatingDashboardTrendPointRead,
    OperatingDataCollectionCountsRead,
    OperatingDataCollectionItemRead,
    OperatingDataCollectionJobRead,
    OperatingDataCollectionRequest,
    OperatingDataCollectionSubmissionRead,
)
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.operating_data import CompassDailyMetrics
from app.platforms.douyin.operating_data_executor import CollectionOutcome
from app.shared.identifiers import generate_id
from app.shared.pagination import PaginationParams


SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")
DOUYIN_CORE_INDEX_SOURCE = "douyin_compass_core_index_v3"
DOUYIN_CORE_INDEX_LEGACY_CONTRACT = "douyin_compass_daily_v1"
DOUYIN_CORE_INDEX_CONTRACT = "douyin_compass_daily_v2_refund_orders"
DOUYIN_CORE_INDEX_ACCEPTED_CONTRACTS = frozenset(
    {
        DOUYIN_CORE_INDEX_LEGACY_CONTRACT,
        DOUYIN_CORE_INDEX_CONTRACT,
    },
)
REFUND_ORDER_STATUS_UNOBSERVED = "unobserved"
REFUND_ORDER_STATUS_AVAILABLE = "available"
REFUND_ORDER_ATTENTION_STATUSES = frozenset(
    {
        "unavailable",
        "not_ready",
        "invalid",
    },
)
COVERAGE_MISSING_SAMPLE_LIMIT = 20
LEGACY_RESPONSE_PARSE_FAILURE_CODE = "DOUYIN_OPERATING_DATA_INVALID_RESPONSE"
LEGACY_RESPONSE_PARSE_FAILURE_STAGE = "response_parse"
COLLECTION_WAITING_FOR_DAILY_BOUNDARY = "COLLECTION_WAITING_FOR_DAILY_BOUNDARY"
DOUYIN_CORE_METRIC_UNKNOWN_FAILURE_CODES = frozenset(
    {
        "DOUYIN_OPERATING_DATA_METRICS_UNAVAILABLE",
        "DOUYIN_OPERATING_DATA_METRICS_NOT_READY",
        "DOUYIN_OPERATING_DATA_CORE_METRIC_MISSING",
    },
)

DashboardSortField = Literal[
    "shop_name",
    "turnover_cents",
    "order_count",
    "refund_order_count",
    "collected_at",
]
DashboardSortDirection = Literal["asc", "desc"]


def is_operating_daily_collection_due(
    *,
    now: datetime,
    local_time: time | None,
) -> bool:
    """Whether the configured Shanghai daily collection boundary has passed.

    Startup recovery and the recurring scheduler must use the same boundary.
    Before it, the prior business day can still be unavailable upstream, so a
    restart must not consume that day's durable ``daily:`` key prematurely.
    """

    if local_time is None:
        return False
    local_now = now.astimezone(SHANGHAI_TIMEZONE)
    return (
        local_now.timetz().replace(tzinfo=None)
        >= local_time.replace(tzinfo=None)
    )


def operating_daily_collection_due_at(
    *,
    business_date: date,
    local_time: time,
) -> datetime:
    """Return the UTC wall-clock boundary for a Shanghai business date.

    A daily request for ``business_date`` becomes eligible on the following
    Shanghai calendar day at the configured collection time.
    """

    return datetime.combine(
        business_date + timedelta(days=1),
        local_time.replace(tzinfo=None),
        tzinfo=SHANGHAI_TIMEZONE,
    ).astimezone(UTC)


def operating_collection_wait_until(
    *,
    business_date: date,
    now: datetime,
    local_time: time | None,
) -> datetime | None:
    """Return a due time only for yesterday before the configured boundary.

    The platform can still be preparing yesterday at the daily collection
    boundary.  That rule must be shared by manual gap
    checks, explicit recollection and executor recovery.  Older completed
    business dates remain immediately eligible; today's date never reaches
    the completed-date APIs.
    """

    if local_time is None:
        return None
    yesterday = _shanghai_today(now) - timedelta(days=1)
    if business_date != yesterday:
        return None
    due_at = operating_daily_collection_due_at(
        business_date=business_date,
        local_time=local_time,
    )
    return due_at if now < due_at else None


@dataclass(frozen=True)
class _ShopRangeValues:
    turnover_cents: int | None
    order_count: int | None
    refund_order_count: int | None
    collected_at: datetime | None
    coverage_complete: bool
    refund_order_coverage_complete: bool
    not_operating_for_range: bool


@dataclass(frozen=True)
class _ManualCollectionPlan:
    """One bounded, authorized update decision before any durable write."""

    business_dates_by_shop: dict[UUID, list[date]]
    active_job_ids: tuple[UUID, ...]
    missing_shop_days: int
    active_shop_days: int
    blocked_shop_days: int
    waiting_shop_days: int
    refund_attention_shop_days: int
    expected_shop_days: int
    not_operating_shop_days: int
    blocked_reasons: tuple[str, ...]


class OperatingDashboardService:
    """Dashboard query, durable collection planning and outcome persistence.

    Platform networking remains in the existing Douyin collector.  This service
    owns no Cookie, signed URL or raw platform response and has no fallback
    data source: it only turns already classified collection outcomes into
    durable, queryable facts.
    """

    def __init__(
        self,
        session: Session,
        *,
        repository: OperatingDashboardRepository | None = None,
        module_access_service: ModuleAccessService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or OperatingDashboardRepository(session)
        self.module_access_service = module_access_service or ModuleAccessService(
            session,
        )
        self.settings = settings or get_settings()

    def read(
        self,
        *,
        actor: ActorContext,
        start_date: date,
        end_date: date,
        platform: ShopPlatform | None,
        shop_id: UUID | None,
        sort_field: DashboardSortField | None,
        sort_direction: DashboardSortDirection | None,
        pagination: PaginationParams,
    ) -> OperatingDashboardRead:
        self._require_dashboard_access(actor)
        self._validate_completed_date_range(start_date, end_date)
        selected_shops = self.repository.list_authorized_shops(
            actor=actor,
            platform=platform,
            shop_id=shop_id,
        )
        all_shops = self.repository.list_authorized_shops(actor=actor)
        selected_range = OperatingDashboardDateRangeRead(
            start_date=start_date,
            end_date=end_date,
        )
        days = _calendar_days(start_date, end_date)
        comparison_range = OperatingDashboardDateRangeRead(
            start_date=start_date - timedelta(days=len(days)),
            end_date=end_date - timedelta(days=len(days)),
        )
        trend_start = end_date - timedelta(days=6) if len(days) == 1 else start_date
        trend_range = OperatingDashboardDateRangeRead(
            start_date=trend_start,
            end_date=end_date,
        )
        metric_start = min(comparison_range.start_date, trend_range.start_date)
        metrics = self.repository.list_metrics(
            shop_ids=(shop.shop_id for shop in selected_shops),
            start_date=metric_start,
            end_date=end_date,
        )
        metric_by_shop_date = {
            (metric.shop_id, metric.business_date): metric for metric in metrics
        }
        supported_shops = [
            shop
            for shop in selected_shops
            if shop.platform is ShopPlatform.DOUYIN and shop.enabled
        ]
        collection_states = self.repository.list_collection_item_states(
            shop_ids=(shop.shop_id for shop in supported_shops),
            start_date=start_date,
            end_date=end_date,
        )

        current_by_shop = self._shop_range_values(
            selected_shops,
            metric_by_shop_date,
            selected_range,
        )
        previous_by_shop = self._shop_range_values(
            selected_shops,
            metric_by_shop_date,
            comparison_range,
        )
        table_rows = self._table_rows(selected_shops, current_by_shop)
        ordered_rows = self._sort_rows(
            table_rows,
            sort_field=sort_field,
            sort_direction=sort_direction,
        )
        total = len(ordered_rows)
        page_rows = ordered_rows[pagination.offset : pagination.offset + pagination.page_size]
        # Unsupported or disabled Shops remain visible in the table and in
        # the selected Shop count, but they must not make confirmed Douyin
        # facts disappear from aggregate cards.  The coverage object below
        # still makes that incomplete scope explicit.
        current_supported_by_shop = {
            shop.shop_id: current_by_shop[shop.shop_id] for shop in supported_shops
        }
        previous_supported_by_shop = {
            shop.shop_id: previous_by_shop[shop.shop_id] for shop in supported_shops
        }
        summary = self._summary(
            current_supported_by_shop,
            previous_supported_by_shop,
            shop_count=total,
            current_core_coverage_complete=self._range_coverage_complete(
                supported_shops,
                metric_by_shop_date,
                selected_range,
            ),
            previous_core_coverage_complete=self._range_coverage_complete(
                supported_shops,
                metric_by_shop_date,
                comparison_range,
            ),
            current_refund_coverage_complete=self._refund_order_range_coverage_complete(
                supported_shops,
                metric_by_shop_date,
                selected_range,
            ),
            previous_refund_coverage_complete=self._refund_order_range_coverage_complete(
                supported_shops,
                metric_by_shop_date,
                comparison_range,
            ),
        )
        trend = self._trend(
            supported_shops,
            metric_by_shop_date,
            trend_range,
        )
        return OperatingDashboardRead(
            date_range=selected_range,
            comparison_date_range=comparison_range,
            trend_date_range=trend_range,
            all_available_shops=[self._shop_option(shop) for shop in all_shops],
            summary=summary,
            trend=trend,
            table=OperatingDashboardTablePageRead(
                items=page_rows,
                total=total,
                page=pagination.page,
                page_size=pagination.page_size,
            ),
            coverage=self._coverage(
                shops=supported_shops,
                metric_by_shop_date=metric_by_shop_date,
                collection_states=collection_states,
                range_value=selected_range,
            ),
            collection_available=self.settings.operating_dashboard_collection_execution_enabled,
        )

    def enqueue_manual_collection(
        self,
        *,
        actor: ActorContext,
        request: OperatingDataCollectionRequest,
        now: datetime | None = None,
    ) -> OperatingDataCollectionJobRead:
        # Compatibility for internal callers; all public and older callers
        # now use the same authorized, deduplicated planning decision.
        result = self.request_collection_update(
            actor=actor, request=request, force_recollect=True, now=now,
        )
        if result.collection_job is None:
            raise OperatingDashboardCollectionRetryUnavailableError()
        return result.collection_job

    def request_collection_update(
        self,
        *,
        actor: ActorContext,
        request: OperatingDataCollectionRequest,
        force_recollect: bool = False,
        now: datetime | None = None,
    ) -> OperatingDataCollectionSubmissionRead:
        """Plan a normal gap-fill or an explicitly requested recollection.

        The dashboard button needs a truthful no-work result:
        a fully collected range must not create an empty Job/Item or make a
        platform request just to look refreshed.
        """

        self._require_dashboard_access(actor)
        if not self.settings.operating_dashboard_collection_execution_enabled:
            raise OperatingDashboardCollectionUnavailableError()
        self._validate_completed_date_range(request.start_date, request.end_date)
        visible_shops = self.repository.list_authorized_shops(
            actor=actor,
            platform=request.platform,
            shop_id=request.shop_id,
        )
        if not visible_shops:
            raise OperatingDashboardShopNotAvailableError()
        supported_shops = [
            shop
            for shop in visible_shops
            if shop.enabled and shop.platform is ShopPlatform.DOUYIN
        ]
        if not supported_shops:
            return OperatingDataCollectionSubmissionRead(
                state="unsupported",
                message="当前筛选范围没有可补齐的已启用抖店",
                collection_job=None,
                missing_shop_days=0,
                queued_shop_days=0,
                active_shop_days=0,
                blocked_shop_days=0,
                refund_attention_shop_days=0,
            )

        resolved_now = now or datetime.now(UTC)
        # The active-item constraint is the final cross-process guard, but a
        # short PostgreSQL advisory lock lets the normal path *reuse* a fresh
        # active row rather than creating a second all-skipped Job after a
        # concurrent button click. The lock ends before any signer/platform
        # work and is a no-op for narrow SQLite unit fixtures.
        try:
            self.repository.acquire_global_claim_lock()
            plan = self._manual_collection_plan(
                shops=supported_shops,
                start_date=request.start_date,
                end_date=request.end_date,
                force_recollect=force_recollect,
                now=resolved_now,
            )
            created_job: OperatingDataCollectionJob | None = None
            if plan.business_dates_by_shop:
                created_job = self._create_collection_job(
                    kind=OperatingCollectionJobKind.MANUAL_REFRESH,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    shops=[
                        shop
                        for shop in supported_shops
                        if shop.shop_id in plan.business_dates_by_shop
                    ],
                    requested_by_user_id=actor.user_id,
                    requested_team_id=actor.team_id,
                    business_dates_by_shop=plan.business_dates_by_shop,
                    now=resolved_now,
                )
            else:
                self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        job_read = (
            self._job_read_for_actor(actor=actor, job=created_job)
            if created_job is not None
            else self._latest_active_job_read_for_actor(
                actor=actor,
                job_ids=plan.active_job_ids,
            )
        )
        queued_shop_days = sum(
            len(dates) for dates in plan.business_dates_by_shop.values()
        )
        if plan.expected_shop_days == 0 and plan.not_operating_shop_days:
            return OperatingDataCollectionSubmissionRead(
                state="not_operating",
                message="所选范围尚未经营，未创建采集任务",
                collection_job=None,
                missing_shop_days=0,
                queued_shop_days=0,
                active_shop_days=0,
                blocked_shop_days=0,
                refund_attention_shop_days=0,
                waiting_shop_days=0,
                not_operating_shop_days=plan.not_operating_shop_days,
            )
        if job_read is not None:
            message = (
                "将重新向平台获取当前筛选范围数据"
                if force_recollect and created_job is not None
                else (
                    f"发现 {queued_shop_days} 个待补采店铺日期，已安排采集"
                    if created_job is not None
                    else "已复用当前范围内的采集进度"
                )
            )
            if plan.blocked_reasons:
                # A partly actionable scope must not hide why the remaining
                # dates stayed terminal. The reason is already sanitized and
                # includes the next safe action where one exists.
                message = f"{message}；{plan.blocked_reasons[0]}"
            return OperatingDataCollectionSubmissionRead(
                state="collection_queued",
                message=message,
                collection_job=job_read,
                missing_shop_days=plan.missing_shop_days,
                queued_shop_days=queued_shop_days,
                active_shop_days=plan.active_shop_days,
                blocked_shop_days=plan.blocked_shop_days,
                waiting_shop_days=plan.waiting_shop_days,
                refund_attention_shop_days=plan.refund_attention_shop_days,
                not_operating_shop_days=plan.not_operating_shop_days,
            )
        if plan.active_shop_days:
            # Authorization can change between the bounded plan and the
            # progress projection. Do not mislabel that unknown active work
            # as "up to date" or create another Job to work around it.
            return OperatingDataCollectionSubmissionRead(
                state="attention_required",
                message="已有采集任务状态已变化，请刷新后查看当前进度",
                collection_job=None,
                missing_shop_days=plan.missing_shop_days,
                queued_shop_days=0,
                active_shop_days=plan.active_shop_days,
                blocked_shop_days=plan.blocked_shop_days,
                waiting_shop_days=plan.waiting_shop_days,
                refund_attention_shop_days=plan.refund_attention_shop_days,
                not_operating_shop_days=plan.not_operating_shop_days,
            )
        if plan.blocked_shop_days:
            return OperatingDataCollectionSubmissionRead(
                state="attention_required",
                message=(
                    plan.blocked_reasons[0]
                    if plan.blocked_reasons
                    else "部分缺口当前不能自动补采，请查看覆盖状态并按提示处理"
                ),
                collection_job=None,
                missing_shop_days=plan.missing_shop_days,
                queued_shop_days=0,
                active_shop_days=0,
                blocked_shop_days=plan.blocked_shop_days,
                waiting_shop_days=plan.waiting_shop_days,
                refund_attention_shop_days=plan.refund_attention_shop_days,
                not_operating_shop_days=plan.not_operating_shop_days,
            )
        if plan.refund_attention_shop_days:
            return OperatingDataCollectionSubmissionRead(
                state="attention_required",
                message="部分退款订单字段暂不可用，请稍后查看或主动重新采集",
                collection_job=None,
                missing_shop_days=plan.missing_shop_days,
                queued_shop_days=0,
                active_shop_days=0,
                blocked_shop_days=0,
                waiting_shop_days=plan.waiting_shop_days,
                refund_attention_shop_days=plan.refund_attention_shop_days,
                not_operating_shop_days=plan.not_operating_shop_days,
            )
        return OperatingDataCollectionSubmissionRead(
            state="up_to_date",
            message="所选范围数据已齐全，无需补采。",
            collection_job=None,
            missing_shop_days=0,
            queued_shop_days=0,
            active_shop_days=0,
            blocked_shop_days=0,
            waiting_shop_days=plan.waiting_shop_days,
            refund_attention_shop_days=0,
            not_operating_shop_days=plan.not_operating_shop_days,
        )

    def enqueue_daily_collection(
        self,
        *,
        business_date: date,
        now: datetime | None = None,
    ) -> OperatingDataCollectionJob:
        """Plan yesterday only, once per Shanghai day.

        Startup reconciles this same daily key after 09:00. Historical
        ranges are selected manually on the dashboard, never inferred.
        """

        resolved_now = now or datetime.now(UTC)
        dedupe_key = f"daily:{business_date.isoformat()}"
        existing = self.repository.get_job_by_dedupe_key(dedupe_key)
        if existing is not None:
            return existing
        shops = self.repository.list_enabled_douyin_shops()
        start_date = business_date
        dates_by_shop = self._manual_collection_plan(
            shops=shops,
            start_date=start_date,
            end_date=business_date,
            force_recollect=False,
            now=resolved_now,
        ).business_dates_by_shop
        return self._create_collection_job(
            kind=OperatingCollectionJobKind.DAILY,
            start_date=start_date,
            end_date=business_date,
            shops=[shop for shop in shops if shop.shop_id in dates_by_shop],
            requested_by_user_id=None,
            dedupe_key=dedupe_key,
            business_dates_by_shop=dates_by_shop,
            now=resolved_now,
        )

    def retry_failed_collection_items(
        self,
        *,
        actor: ActorContext,
        collection_job_id: UUID,
        item_ids: Iterable[UUID],
        now: datetime | None = None,
    ) -> OperatingDataCollectionJobRead:
        self._require_dashboard_access(actor)
        if not self.settings.operating_dashboard_collection_execution_enabled:
            raise OperatingDashboardCollectionUnavailableError()
        if self.repository.get_job(collection_job_id) is None:
            raise OperatingDashboardCollectionNotFoundError()
        visible_items = self.repository.list_job_items_for_actor(
            actor=actor,
            collection_job_id=collection_job_id,
        )
        if not visible_items:
            raise OperatingDashboardCollectionNotFoundError()
        requested_ids = set(item_ids)
        # A broad retry request must stay limited to rows already marked
        # retryable.  The parser-specific manual recovery is intentionally
        # explicit per original item so it cannot become a generic retry-all
        # endpoint for terminal failures.
        candidate_items = [
            item
            for item in visible_items
            if item.status == OperatingCollectionItemStatus.FAILED.value
            and (
                (
                    item.retryable
                    and (
                        not requested_ids
                        or item.collection_item_id in requested_ids
                    )
                )
                or (
                    bool(requested_ids)
                    and item.collection_item_id in requested_ids
                    and item.failure_code == LEGACY_RESPONSE_PARSE_FAILURE_CODE
                    and item.failure_stage == LEGACY_RESPONSE_PARSE_FAILURE_STAGE
                )
            )
        ]
        if not candidate_items:
            raise OperatingDashboardCollectionRetryUnavailableError()
        shops = self.repository.list_authorized_shops(actor=actor)
        by_id = {shop.shop_id: shop for shop in shops}
        resolved_now = now or datetime.now(UTC)
        retry_dates_by_shop: dict[UUID, list[date]] = defaultdict(list)
        job: OperatingDataCollectionJob | None = None
        try:
            self.repository.acquire_global_claim_lock()
            states_by_shop_date: dict[
                tuple[UUID, date],
                list[CollectionItemState],
            ] = defaultdict(list)
            for state in self.repository.list_collection_item_states(
                shop_ids={item.shop_id for item in candidate_items},
                start_date=min(item.business_date for item in candidate_items),
                end_date=max(item.business_date for item in candidate_items),
            ):
                states_by_shop_date[(state.shop_id, state.business_date)].append(state)
            for item in candidate_items:
                if item.shop_id not in by_id:
                    continue
                history = states_by_shop_date[(item.shop_id, item.business_date)]
                latest = _latest_state(history)
                # Do not allow a stale UI item to reopen a newer terminal or
                # active row.  `find_active_item` inside `_new_item` is the
                # final DB guard; this comparison makes the user result
                # truthful before a new Job is written.
                if latest is None or latest.collection_item_id != item.collection_item_id:
                    continue
                if not self._manual_gap_recovery_allowed(
                    history,
                    now=resolved_now,
                    allow_response_parse_recovery=(
                        item.collection_item_id in requested_ids
                    ),
                ):
                    continue
                retry_dates_by_shop[item.shop_id].append(item.business_date)
            if retry_dates_by_shop:
                job = self._create_collection_job(
                    kind=OperatingCollectionJobKind.RETRY,
                    start_date=min(
                        business_date
                        for dates in retry_dates_by_shop.values()
                        for business_date in dates
                    ),
                    end_date=max(
                        business_date
                        for dates in retry_dates_by_shop.values()
                        for business_date in dates
                    ),
                    shops=[by_id[shop_id] for shop_id in retry_dates_by_shop],
                    requested_by_user_id=actor.user_id,
                    requested_team_id=actor.team_id,
                    business_dates_by_shop=retry_dates_by_shop,
                    now=resolved_now,
                )
        except Exception:
            self.session.rollback()
            raise
        if job is None:
            # Release the advisory-lock transaction without pretending the
            # caller's stale/blocked item selection was a successful retry.
            self.session.rollback()
            raise OperatingDashboardCollectionRetryUnavailableError()
        return self._job_read_for_actor(actor=actor, job=job)

    def get_collection_job(
        self,
        *,
        actor: ActorContext,
        collection_job_id: UUID,
    ) -> OperatingDataCollectionJobRead:
        self._require_dashboard_access(actor)
        job = self.repository.get_job(collection_job_id)
        if job is None:
            raise OperatingDashboardCollectionNotFoundError()
        return self._job_read_for_actor(actor=actor, job=job)

    def resume_after_session_refresh(
        self,
        shop_id: UUID,
        *,
        now: datetime | None = None,
    ) -> int:
        resolved_now = now or datetime.now(UTC)
        skipped = self.skip_not_operating_collection_items(
            shop_id=shop_id,
            now=resolved_now,
        )
        job_ids = self.repository.paused_job_ids_for_shop(shop_id)
        resumed = self.repository.resume_paused_reauthorization(
            shop_id=shop_id,
            now=resolved_now,
        )
        deferred = self._defer_yesterday_until_daily_boundary(
            now=resolved_now,
            shop_id=shop_id,
        )
        if resumed:
            self.repository.update_job_statuses(job_ids, now=resolved_now)
        # Resume only original requested rows, without creating historical work.
        if resumed or deferred or skipped:
            self.session.commit()
        return resumed

    def has_confirmed_metric_before(
        self,
        *,
        shop_id: UUID,
        operating_start_date: date,
    ) -> bool:
        """Expose the boundary-conflict check to the Shop edit transaction."""

        return self.repository.has_confirmed_metric_before(
            shop_id=shop_id,
            business_date=operating_start_date,
        )

    def skip_not_operating_collection_items(
        self,
        *,
        shop_id: UUID,
        now: datetime,
    ) -> int:
        """Stop unstarted work made out-of-scope by a confirmed boundary."""

        job_ids = self.repository.affected_job_ids_for_not_operating_items(
            shop_id=shop_id,
        )
        skipped = self.repository.mark_not_operating_items_skipped(
            now=now,
            shop_id=shop_id,
        )
        if skipped:
            self.repository.update_job_statuses(job_ids, now=now)
        return skipped

    def recover_after_backend_startup(
        self,
        *,
        now: datetime | None = None,
        collection_job_id: UUID | None = None,
    ) -> OperatingDataCollectionJob | None:
        """Recover durable work and reconcile yesterday only after the daily boundary.

        The caller gates this to the explicit automatic-collection switches.
        This function performs only short database transactions; it never
        waits for the executor, Session validation, signing, or the platform.
        A controlled collection_job_id narrows recovery only; the default
        startup path remains global.
        """

        resolved_now = now or datetime.now(UTC)
        try:
            self.repository.acquire_global_claim_lock()
            self._recover_expired_or_disabled_items(
                now=resolved_now,
                collection_job_id=collection_job_id,
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        if not is_operating_daily_collection_due(
            now=resolved_now,
            local_time=self.settings.operating_dashboard_daily_collection_local_time,
        ):
            # A restart before the configured collection time may recover
            # leases and disabled items, but it must not reserve the stable
            # daily key before Compass is expected to publish yesterday.
            return None
        business_date = _shanghai_today(resolved_now) - timedelta(days=1)
        return self.enqueue_daily_collection(
            business_date=business_date,
            now=resolved_now,
        )

    def prepare_next_collection(
        self,
        *,
        now: datetime,
        lease_until: datetime,
        collection_job_id: UUID | None = None,
    ) -> CollectionClaim | None:
        try:
            # PostgreSQL advisory locking makes the global running count and
            # the following claim one short serializable decision.  The lock
            # is released by this commit before any Session/Signer/platform
            # work starts, so it never turns external I/O into a DB lock.
            self.repository.acquire_global_claim_lock()
            self._recover_expired_or_disabled_items(
                now=now,
                collection_job_id=collection_job_id,
            )
            self._defer_yesterday_until_daily_boundary(
                now=now,
                collection_job_id=collection_job_id,
            )
            if (
                self.repository.count_running_items()
                >= self.settings.douyin_compass_collection_concurrency
            ):
                self.session.commit()
                return None
            claim = self.repository.claim_next(
                now=now,
                lease_until=lease_until,
                collection_job_id=collection_job_id,
            )
            self.session.commit()
            return claim
        except IntegrityError as error:
            # Two Backend processes can observe different pending dates for
            # the same Shop before either transaction commits.  PostgreSQL's
            # partial unique index is the cross-process authority: losing the
            # race is normal, must not invoke the platform, and leaves the
            # unclaimed item pending for a later scan.
            self.session.rollback()
            if _is_running_shop_claim_conflict(error):
                return None
            raise

    def _recover_expired_or_disabled_items(
        self,
        *,
        now: datetime,
        collection_job_id: UUID | None = None,
    ) -> None:
        """Apply database-only executor recovery while the caller holds its lock."""

        expired_job_ids = self.repository.affected_job_ids_for_expired_running_items(
            now=now,
            collection_job_id=collection_job_id,
        )
        disabled_job_ids = self.repository.affected_job_ids_for_disabled_pending_items(
            collection_job_id=collection_job_id,
        )
        not_operating_job_ids = self.repository.affected_job_ids_for_not_operating_items(
            collection_job_id=collection_job_id,
        )
        expired = self.repository.mark_expired_running_items_pending(
            now=now,
            collection_job_id=collection_job_id,
        )
        skipped = self.repository.mark_disabled_pending_items_skipped(
            now=now,
            collection_job_id=collection_job_id,
        )
        not_operating_skipped = self.repository.mark_not_operating_items_skipped(
            now=now,
            collection_job_id=collection_job_id,
        )
        if expired or skipped or not_operating_skipped:
            self.repository.update_job_statuses(
                (*expired_job_ids, *disabled_job_ids, *not_operating_job_ids),
                now=now,
            )

    def _defer_yesterday_until_daily_boundary(
        self,
        *,
        now: datetime,
        shop_id: UUID | None = None,
        collection_job_id: UUID | None = None,
    ) -> tuple[UUID, ...]:
        """Apply the shared eligibility rule to already durable pending rows.

        New jobs calculate the same delay in `_new_item`.  This extra
        database-side pass covers a row resumed after reauthorization and a
        row written by an older Backend process, before `claim_next` could
        turn it into a platform request.
        """

        yesterday = _shanghai_today(now) - timedelta(days=1)
        local_time = self.settings.operating_dashboard_daily_collection_local_time
        wait_until = operating_collection_wait_until(
            business_date=yesterday,
            now=now,
            local_time=local_time,
        )
        if wait_until is not None:
            job_ids = self.repository.defer_pending_items_until(
                business_date=yesterday,
                available_at=wait_until,
                now=now,
                shop_id=shop_id,
                collection_job_id=collection_job_id,
            )
        else:
            return ()
        if job_ids:
            self.repository.update_job_statuses(job_ids, now=now)
        return job_ids


    def _manual_collection_plan(
        self,
        *,
        shops: list[DashboardShop],
        start_date: date,
        end_date: date,
        force_recollect: bool,
        now: datetime,
    ) -> _ManualCollectionPlan:
        """Find only actionable Shop/date work in one bounded read pass.

        A normal update queues missing core facts and one unobserved refund
        observation. An explicit recollection additionally queues checked
        dates, but neither mode bypasses an active item, a paused
        reauthorization, or a terminal non-retryable platform result, except
        for a bounded, explicitly requested response_parse recovery.
        """

        shop_ids = tuple(shop.shop_id for shop in shops)
        metric_by_shop_date = {
            (metric.shop_id, metric.business_date): metric
            for metric in self.repository.list_metrics(
                shop_ids=shop_ids,
                start_date=start_date,
                end_date=end_date,
            )
        }
        states_by_shop_date: dict[tuple[UUID, date], list[CollectionItemState]] = defaultdict(
            list,
        )
        for state in self.repository.list_collection_item_states(
            shop_ids=shop_ids,
            start_date=start_date,
            end_date=end_date,
        ):
            states_by_shop_date[(state.shop_id, state.business_date)].append(state)

        candidates: dict[UUID, list[date]] = defaultdict(list)
        active_job_ids: set[UUID] = set()
        missing_shop_days = 0
        active_shop_days = 0
        blocked_shop_days = 0
        waiting_shop_days = 0
        refund_attention_shop_days = 0
        expected_shop_days = 0
        not_operating_shop_days = 0
        blocked_reasons: list[str] = []
        for shop in shops:
            expected_dates = _expected_dates_for_shop(shop, start_date, end_date)
            expected_shop_days += len(expected_dates)
            not_operating_shop_days += _not_operating_days_in_range(
                shop,
                start_date,
                end_date,
            )
            for business_date in reversed(expected_dates):
                metric = metric_by_shop_date.get((shop.shop_id, business_date))
                requires_collection = _requires_collection(metric)
                refund_attention = _refund_order_requires_attention(metric)
                history = states_by_shop_date[(shop.shop_id, business_date)]
                active_states = [
                    state
                    for state in history
                    if state.status
                    in {
                        OperatingCollectionItemStatus.PENDING.value,
                        OperatingCollectionItemStatus.RUNNING.value,
                        OperatingCollectionItemStatus.PAUSED_REAUTHORIZATION.value,
                    }
                ]
                if requires_collection:
                    missing_shop_days += 1
                elif refund_attention:
                    refund_attention_shop_days += 1
                if active_states:
                    # Active durable work owns this Shop/date even if a prior
                    # successful fact exists and the user explicitly asks to
                    # recollect it. Reusing it avoids duplicate platform I/O.
                    active_shop_days += 1
                    if any(
                        state.status == OperatingCollectionItemStatus.PENDING.value
                        and state.failure_code
                        == COLLECTION_WAITING_FOR_DAILY_BOUNDARY
                        for state in active_states
                    ):
                        waiting_shop_days += 1
                    active_job_ids.update(
                        state.collection_job_id for state in active_states
                    )
                    continue
                if not requires_collection and not force_recollect:
                    continue
                # An explicit recollection is intentional, but it is not an
                # escape hatch for a terminal platform/session result or an
                # in-cooldown retryable failure.  A confirmed historical
                # fact remains readable in either case; the blocked result
                # simply prevents this button from issuing another request.
                if not self._manual_gap_recovery_allowed(
                    history,
                    now=now,
                    allow_response_parse_recovery=force_recollect,
                ):
                    blocked_shop_days += 1
                    reason = self._manual_recovery_block_reason(
                        history,
                        now=now,
                        allow_response_parse_recovery=force_recollect,
                    )
                    if reason not in blocked_reasons:
                        blocked_reasons.append(reason)
                    continue
                candidates[shop.shop_id].append(business_date)
                if (
                    operating_collection_wait_until(
                        business_date=business_date,
                        now=now,
                        local_time=self.settings.operating_dashboard_daily_collection_local_time,
                    )
                    is not None
                ):
                    waiting_shop_days += 1
        return _ManualCollectionPlan(
            business_dates_by_shop=dict(candidates),
            active_job_ids=tuple(active_job_ids),
            missing_shop_days=missing_shop_days,
            active_shop_days=active_shop_days,
            blocked_shop_days=blocked_shop_days,
            waiting_shop_days=waiting_shop_days,
            refund_attention_shop_days=refund_attention_shop_days,
            expected_shop_days=expected_shop_days,
            not_operating_shop_days=not_operating_shop_days,
            blocked_reasons=tuple(blocked_reasons),
        )

    def _manual_gap_recovery_allowed(
        self,
        states: Iterable[CollectionItemState],
        *,
        now: datetime,
        allow_response_parse_recovery: bool = False,
    ) -> bool:
        """Apply the same finite safeguards to ordinary dashboard updates.

        Explicit retry remains a separate, deliberate action. Repeated clicks
        on the normal "check and fill" control must not create an unlimited
        series of attempts after a session, risk, or non-retryable failure.
        Explicit parser recovery uses the same cooldown and cumulative
        failure budget. A successful attempt ends that failure chain.
        """

        history = list(states)
        if not history:
            return True
        if any(
            state.status in {
                OperatingCollectionItemStatus.PENDING.value,
                OperatingCollectionItemStatus.RUNNING.value,
                OperatingCollectionItemStatus.PAUSED_REAUTHORIZATION.value,
            }
            for state in history
        ):
            return False
        latest = _latest_state(history)
        if latest is None or latest.status != OperatingCollectionItemStatus.FAILED.value:
            return True
        if not latest.retryable and not (
            allow_response_parse_recovery and _is_response_parse_failure(latest)
        ):
            return False
        cooldown = timedelta(
            seconds=self.settings.operating_dashboard_gap_recovery_retry_cooldown_seconds,
        )
        return (
            latest.updated_at + cooldown <= now
            and _attempts_since_last_success(history)
            < self.settings.operating_dashboard_collection_max_attempts
        )

    def _manual_recovery_block_reason(
        self,
        states: Iterable[CollectionItemState],
        *,
        now: datetime,
        allow_response_parse_recovery: bool,
    ) -> str:
        """Return a safe action-oriented explanation without raw platform text."""

        latest = _latest_state(states)
        if latest is None:
            return "当前范围暂不能补采，请刷新后重试"
        if latest.failure_code in {
            "SHOP_REAUTHORIZATION_REQUIRED",
            "SHOP_SESSION_IDENTITY_MISMATCH",
            "SHOP_SESSION_VERSION_CONFLICT",
        }:
            return "店铺需要重新登录后才能继续采集"
        if latest.failure_code in DOUYIN_CORE_METRIC_UNKNOWN_FAILURE_CODES:
            return "平台指标未知，暂不能补采"
        if _is_response_parse_failure(latest):
            if not allow_response_parse_recovery:
                return "历史响应解析失败，可使用“重新采集当前筛选范围”发起有限恢复"
            cooldown = timedelta(
                seconds=self.settings.operating_dashboard_gap_recovery_retry_cooldown_seconds,
            )
            if latest.updated_at + cooldown > now:
                return "解析恢复仍在冷却期，请稍后再试"
            return "解析恢复已达到重采上限，请等待人工核实"
        if latest.retryable:
            cooldown = timedelta(
                seconds=self.settings.operating_dashboard_gap_recovery_retry_cooldown_seconds,
            )
            if latest.updated_at + cooldown > now:
                return "采集仍在冷却期，请稍后再试"
            return "采集已达到重试上限，请等待人工核实"
        return "平台返回暂不能自动恢复，请核实店铺登录或平台状态"

    def abandon_claim_if_not_executable(
        self,
        claim: CollectionClaim,
        *,
        now: datetime | None = None,
    ) -> bool:
        """Last authorization and time-eligibility check before external I/O."""

        item = self.repository.get_item_for_update(
            collection_item_id=claim.collection_item_id,
        )
        if (
            item is None
            or item.status != OperatingCollectionItemStatus.RUNNING.value
            or item.attempt_count != claim.attempt_count
        ):
            self.session.rollback()
            return True
        if not self._manual_claim_still_authorized(item):
            resolved_now = now or datetime.now(UTC)
            self._skip_claim(
                item,
                now=resolved_now,
                failure_code="COLLECTION_REQUESTER_ACCESS_REVOKED",
                failure_message="发起更新所需的当前授权已撤销，未发起平台请求",
            )
            return True
        resolved_now = now or datetime.now(UTC)
        wait_until = operating_collection_wait_until(
            business_date=claim.business_date,
            now=resolved_now,
            local_time=self.settings.operating_dashboard_daily_collection_local_time,
        )
        if wait_until is not None:
            # A legacy process could claim a row just as this Feature deploys.
            # No platform call has happened yet, so return it to PENDING and
            # undo that claim's attempt increment instead of recording a
            # synthetic failure.
            item.status = OperatingCollectionItemStatus.PENDING.value
            item.attempt_count = max(0, item.attempt_count - 1)
            item.retryable = True
            item.retry_after = wait_until
            item.failure_code = COLLECTION_WAITING_FOR_DAILY_BOUNDARY
            item.failure_message = "等待每日采集时间后再请求平台"
            item.failure_stage = "queued"
            item.lease_until = None
            item.started_at = None
            item.finished_at = None
            item.updated_at = resolved_now
            self.repository.update_job_statuses((item.collection_job_id,), now=resolved_now)
            self.session.commit()
            return True
        shop = self.repository.get_shop(claim.shop_id)
        if (
            shop is not None
            and shop.enabled
            and shop.deleted_at is None
            and (
                shop.operating_start_date is None
                or claim.business_date >= shop.operating_start_date
            )
        ):
            self.session.rollback()
            return False
        if (
            shop is not None
            and shop.operating_start_date is not None
            and claim.business_date < shop.operating_start_date
        ):
            self._skip_claim(
                item,
                now=resolved_now,
                failure_code="SHOP_NOT_OPERATING_ON_DATE",
                failure_message="该业务日期早于已确认经营起算日，未发起平台请求",
            )
            return True
        self._skip_claim(
            item,
            now=resolved_now,
            failure_code="SHOP_DISABLED",
            failure_message="店铺已停用或移除，未发起平台请求",
        )
        return True

    def _manual_claim_still_authorized(
        self,
        item: OperatingDataCollectionItem,
    ) -> bool:
        """Re-resolve a human request before its first external call.

        System-created backfills have no human requester.  Manual refresh and
        retry jobs keep both the requester and the selected Team, so a member
        move, disabled account, module revocation or shop-access revocation
        takes effect even if it happened after enqueueing.
        """

        job = self.repository.get_job(item.collection_job_id)
        if job is None:
            return False
        if job.kind not in {
            OperatingCollectionJobKind.MANUAL_REFRESH.value,
            OperatingCollectionJobKind.RETRY.value,
        }:
            return True
        if job.requested_by_user_id is None:
            return False
        try:
            actor = ActorContextService(self.session).resolve(
                user_id=job.requested_by_user_id,
                requested_team_id=job.requested_team_id,
            )
            self._require_dashboard_access(actor)
        except AppError:
            return False
        return (
            self.repository.get_authorized_shop(
                actor=actor,
                shop_id=item.shop_id,
            )
            is not None
        )

    def _skip_claim(
        self,
        item: OperatingDataCollectionItem,
        *,
        now: datetime,
        failure_code: str,
        failure_message: str,
    ) -> None:
        item.status = OperatingCollectionItemStatus.SKIPPED.value
        item.retryable = False
        item.failure_code = failure_code
        item.failure_message = failure_message
        item.failure_stage = "queued"
        item.lease_until = None
        item.finished_at = now
        item.updated_at = now
        self.repository.update_job_statuses((item.collection_job_id,), now=now)
        self.session.commit()

    def finalize_collection(
        self,
        *,
        claim: CollectionClaim,
        outcome: CollectionOutcome,
        now: datetime,
    ) -> bool:
        item = self.repository.get_item_for_update(
            collection_item_id=claim.collection_item_id,
        )
        if (
            item is None
            or item.status != OperatingCollectionItemStatus.RUNNING.value
            or item.attempt_count != claim.attempt_count
        ):
            self.session.rollback()
            return False
        if outcome.status.value == "succeeded" and outcome.metrics is not None:
            self._persist_success(item, outcome.metrics, now)
        elif outcome.requires_reauthorization:
            self._pause_for_reauthorization(item, outcome, now)
        elif outcome.retryable and _attempts_since_last_success(
            self.repository.list_collection_item_states(
                shop_ids=(item.shop_id,),
                start_date=item.business_date,
                end_date=item.business_date,
            ),
        ) < self.settings.operating_dashboard_collection_max_attempts:
            self._retry_later(item, outcome, now)
        else:
            self._fail(item, outcome, now)
        self._record_timings(item, claim=claim, outcome=outcome, now=now)
        self.repository.update_job_statuses((item.collection_job_id,), now=now)
        self.session.commit()
        return True

    def _create_collection_job(
        self,
        *,
        kind: OperatingCollectionJobKind,
        start_date: date,
        end_date: date,
        shops: list[DashboardShop],
        requested_by_user_id: UUID | None,
        requested_team_id: UUID | None = None,
        dedupe_key: str | None = None,
        business_dates: list[date] | None = None,
        business_dates_by_shop: dict[UUID, list[date]] | None = None,
        now: datetime | None = None,
        commit: bool = True,
    ) -> OperatingDataCollectionJob:
        # A concurrent enqueue can collide only with an active Shop/date item.
        # Retry the transaction once so the second request records explicit
        # SKIPPED rows rather than exposing a database uniqueness error.
        resolved_now = now or datetime.now(UTC)
        for attempt in range(2):
            try:
                with self.session.begin_nested():
                    if dedupe_key is not None:
                        existing = self.repository.get_job_by_dedupe_key(dedupe_key)
                        if existing is not None:
                            return existing
                    job = OperatingDataCollectionJob(
                        collection_job_id=generate_id(),
                        kind=kind.value,
                        status=OperatingCollectionJobStatus.PENDING.value,
                        requested_start_date=start_date,
                        requested_end_date=end_date,
                        requested_by_user_id=requested_by_user_id,
                        requested_team_id=requested_team_id,
                        dedupe_key=dedupe_key,
                    )
                    self.repository.add_job(job)
                    self.session.flush()
                    priority = 0
                    for shop, business_date in _prioritized_collection_items(
                        shops=shops,
                        start_date=start_date,
                        end_date=end_date,
                        business_dates=business_dates,
                        business_dates_by_shop=business_dates_by_shop,
                    ):
                        item = self._new_item(
                            job=job,
                            shop=shop,
                            business_date=business_date,
                            priority=priority,
                            now=resolved_now,
                        )
                        priority += 1
                        self.repository.add_item(item)
                    self.repository.update_job_statuses(
                        (job.collection_job_id,),
                        now=resolved_now,
                    )
                    self.session.flush()
                if not commit:
                    return job
                self.session.commit()
                self.session.refresh(job)
                return job
            except IntegrityError:
                if attempt:
                    self.session.rollback()
                    raise
        raise AssertionError("unreachable")

    def _new_item(
        self,
        *,
        job: OperatingDataCollectionJob,
        shop: DashboardShop,
        business_date: date,
        priority: int,
        now: datetime,
    ) -> OperatingDataCollectionItem:
        active = self.repository.find_active_item(
            shop_id=shop.shop_id,
            business_date=business_date,
        )
        if not shop.enabled:
            return OperatingDataCollectionItem(
                collection_item_id=generate_id(),
                collection_job_id=job.collection_job_id,
                shop_id=shop.shop_id,
                business_date=business_date,
                status=OperatingCollectionItemStatus.SKIPPED.value,
                priority=priority,
                retryable=False,
                failure_code="SHOP_DISABLED",
                failure_message="店铺已停用，未发起平台请求",
                failure_stage="queued",
                finished_at=now,
            )
        if shop.platform is not ShopPlatform.DOUYIN:
            return OperatingDataCollectionItem(
                collection_item_id=generate_id(),
                collection_job_id=job.collection_job_id,
                shop_id=shop.shop_id,
                business_date=business_date,
                status=OperatingCollectionItemStatus.SKIPPED.value,
                priority=priority,
                retryable=False,
                failure_code="PLATFORM_OPERATING_DATA_UNSUPPORTED",
                failure_message="当前平台尚未接入经营数据采集",
                failure_stage="queued",
                finished_at=now,
            )
        if active is not None:
            return OperatingDataCollectionItem(
                collection_item_id=generate_id(),
                collection_job_id=job.collection_job_id,
                shop_id=shop.shop_id,
                business_date=business_date,
                status=OperatingCollectionItemStatus.SKIPPED.value,
                priority=priority,
                retryable=False,
                failure_code="COLLECTION_ALREADY_QUEUED",
                failure_message="该店铺日期已有进行中的采集",
                failure_stage="queued",
                finished_at=now,
            )
        wait_until = operating_collection_wait_until(
            business_date=business_date,
            now=now,
            local_time=self.settings.operating_dashboard_daily_collection_local_time,
        )
        return OperatingDataCollectionItem(
            collection_item_id=generate_id(),
            collection_job_id=job.collection_job_id,
            shop_id=shop.shop_id,
            business_date=business_date,
            status=OperatingCollectionItemStatus.PENDING.value,
            priority=priority,
            retryable=True,
            retry_after=wait_until,
            failure_code=(
                COLLECTION_WAITING_FOR_DAILY_BOUNDARY
                if wait_until is not None
                else None
            ),
            failure_message=(
                "等待每日采集时间后再请求平台"
                if wait_until is not None
                else None
            ),
            failure_stage="queued" if wait_until is not None else None,
        )

    def _job_read_for_actor(
        self,
        *,
        actor: ActorContext,
        job: OperatingDataCollectionJob,
    ) -> OperatingDataCollectionJobRead:
        items = self.repository.list_job_items_for_actor(
            actor=actor,
            collection_job_id=job.collection_job_id,
        )
        if not items:
            raise OperatingDashboardCollectionNotFoundError()
        return self._job_read(job, items)

    def _latest_active_job_read_for_actor(
        self,
        *,
        actor: ActorContext,
        job_ids: Iterable[UUID],
    ) -> OperatingDataCollectionJobRead | None:
        """Return one already-authorized active Job for UI progress polling.

        A bounded request can overlap several existing Jobs. The full
        coverage state remains the source of truth for all Shop/dates; the
        latest visible Job gives the existing UI one real progress stream
        without manufacturing another Job solely for tracking.
        """

        jobs = [
            job
            for job_id in set(job_ids)
            if (job := self.repository.get_job(job_id)) is not None
        ]
        for job in sorted(
            jobs,
            key=lambda value: (value.updated_at, str(value.collection_job_id)),
            reverse=True,
        ):
            try:
                return self._job_read_for_actor(actor=actor, job=job)
            except OperatingDashboardCollectionNotFoundError:
                # A concurrent access revocation can make one related Job
                # invisible between planning and response. It is not a reason
                # to reveal another Team's state or create duplicate work.
                continue
        return None

    @staticmethod
    def _job_read(
        job: OperatingDataCollectionJob,
        items: list[OperatingDataCollectionItem],
    ) -> OperatingDataCollectionJobRead:
        counts = Counter(item.status for item in items)
        return OperatingDataCollectionJobRead(
            collection_job_id=job.collection_job_id,
            kind=job.kind,
            status=_derive_job_status(items),
            requested_start_date=job.requested_start_date,
            requested_end_date=job.requested_end_date,
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            counts=OperatingDataCollectionCountsRead(
                pending=counts[OperatingCollectionItemStatus.PENDING.value],
                running=counts[OperatingCollectionItemStatus.RUNNING.value],
                succeeded=counts[OperatingCollectionItemStatus.SUCCEEDED.value],
                failed=counts[OperatingCollectionItemStatus.FAILED.value],
                skipped=counts[OperatingCollectionItemStatus.SKIPPED.value],
                paused_reauthorization=counts[
                    OperatingCollectionItemStatus.PAUSED_REAUTHORIZATION.value
                ],
            ),
            items=[
                OperatingDataCollectionItemRead(
                    collection_item_id=item.collection_item_id,
                    shop_id=item.shop_id,
                    business_date=item.business_date,
                    status=item.status,
                    retryable=item.retryable,
                    failure_code=item.failure_code,
                    failure_message=item.failure_message,
                    failure_stage=item.failure_stage,
                    attempt_count=item.attempt_count,
                    started_at=item.started_at,
                    finished_at=item.finished_at,
                    queue_wait_ms=item.queue_wait_ms,
                    session_preparation_ms=item.session_preparation_ms,
                    signature_ms=item.signature_ms,
                    platform_response_ms=item.platform_response_ms,
                    response_parse_ms=item.response_parse_ms,
                    total_ms=item.total_ms,
                )
                for item in items
            ],
        )

    def _persist_success(
        self,
        item: OperatingDataCollectionItem,
        metrics: CompassDailyMetrics,
        now: datetime,
    ) -> None:
        self.repository.upsert_daily_metric(
            shop_id=item.shop_id,
            business_date=item.business_date,
            source_code=DOUYIN_CORE_INDEX_SOURCE,
            metric_contract=DOUYIN_CORE_INDEX_CONTRACT,
            turnover_cents=metrics.income_amt_cents,
            order_count=metrics.pay_cnt,
            refund_order_count=metrics.refund_order_count,
            refund_order_status=metrics.refund_order_status,
            collected_at=now,
        )
        item.status = OperatingCollectionItemStatus.SUCCEEDED.value
        item.retryable = False
        item.retry_after = None
        item.failure_code = None
        item.failure_message = None
        item.failure_stage = None
        item.lease_until = None
        item.finished_at = now
        item.updated_at = now

    def _pause_for_reauthorization(
        self,
        item: OperatingDataCollectionItem,
        outcome: CollectionOutcome,
        now: datetime,
    ) -> None:
        item.status = OperatingCollectionItemStatus.PAUSED_REAUTHORIZATION.value
        item.retryable = False
        item.retry_after = None
        item.failure_code = outcome.failure_code
        item.failure_message = "店铺登录态需要重新授权"
        item.failure_stage = outcome.stage.value
        item.lease_until = None
        item.finished_at = now
        item.updated_at = now
        paused_job_ids = self.repository.pause_pending_for_reauthorization(
            shop_id=item.shop_id,
            now=now,
            failure_code=outcome.failure_code or "SHOP_REAUTHORIZATION_REQUIRED",
        )
        self.repository.update_job_statuses(
            (*paused_job_ids, item.collection_job_id),
            now=now,
        )

    def _retry_later(
        self,
        item: OperatingDataCollectionItem,
        outcome: CollectionOutcome,
        now: datetime,
    ) -> None:
        delay_seconds = self.settings.operating_dashboard_collection_retry_base_seconds * (
            2 ** max(0, item.attempt_count - 1)
        )
        item.status = OperatingCollectionItemStatus.PENDING.value
        item.retryable = True
        item.retry_after = now + timedelta(seconds=delay_seconds)
        item.failure_code = outcome.failure_code
        item.failure_message = outcome.failure_message or _safe_failure_message(
            outcome.failure_code,
        )
        item.failure_stage = outcome.stage.value
        item.lease_until = None
        item.finished_at = None
        item.updated_at = now

    def _fail(
        self,
        item: OperatingDataCollectionItem,
        outcome: CollectionOutcome,
        now: datetime,
    ) -> None:
        item.status = OperatingCollectionItemStatus.FAILED.value
        item.retryable = outcome.retryable
        item.retry_after = None
        item.failure_code = outcome.failure_code
        item.failure_message = outcome.failure_message or _safe_failure_message(
            outcome.failure_code,
        )
        item.failure_stage = outcome.stage.value
        item.lease_until = None
        item.finished_at = now
        item.updated_at = now

    @staticmethod
    def _record_timings(
        item: OperatingDataCollectionItem,
        *,
        claim: CollectionClaim,
        outcome: CollectionOutcome,
        now: datetime,
    ) -> None:
        queue_wait_ms = max(0, round((now - claim.queued_at).total_seconds() * 1000))
        item.queue_wait_ms = queue_wait_ms
        item.session_preparation_ms = outcome.timings.session_preparation_ms
        item.signature_ms = outcome.timings.signature_ms
        item.platform_response_ms = outcome.timings.platform_response_ms
        item.response_parse_ms = outcome.timings.response_parse_ms
        item.total_ms = outcome.timings.total_ms

    @staticmethod
    def _shop_option(shop: DashboardShop) -> OperatingDashboardShopOptionRead:
        return OperatingDashboardShopOptionRead(
            shop_id=shop.shop_id,
            shop_name=shop.shop_name,
            platform=shop.platform,
        )

    def _coverage(
        self,
        *,
        shops: list[DashboardShop],
        metric_by_shop_date: dict[tuple[UUID, date], ShopOperatingDailyMetric],
        collection_states: Iterable[CollectionItemState],
        range_value: OperatingDashboardDateRangeRead,
    ) -> OperatingDashboardCoverageRead:
        """Describe data availability without initiating collection work.

        Coverage is scoped to already-authorized, enabled, supported Shops.
        It is deliberately a database-read result: an empty/failed platform
        request is never represented as a zero or as a fake completed day.
        """

        if not shops:
            return OperatingDashboardCoverageRead(
                state="unsupported",
                supported_shop_count=0,
                collected_shop_days=0,
                total_shop_days=0,
                missing_shop_days=0,
                missing_samples=[],
                missing_samples_truncated=False,
                manual_backfill_required=False,
                not_operating_shop_days=0,
                shops_with_unknown_operating_start=0,
                no_operating_scope=False,
            )
        latest_states = _latest_collection_states(collection_states)
        missing: list[OperatingDashboardCoverageMissingRead] = []
        collected = 0
        dates = _calendar_days(range_value.start_date, range_value.end_date)
        total = 0
        not_operating_shop_days = 0
        shops_with_unknown_operating_start = 0
        shop_by_id = {shop.shop_id: shop for shop in shops}
        for shop_id, shop in sorted(
            shop_by_id.items(),
            key=lambda item: (item[1].shop_name.casefold(), str(item[0])),
        ):
            if shop.operating_start_date is None:
                shops_with_unknown_operating_start += 1
            expected_dates = _expected_dates_for_shop(
                shop,
                range_value.start_date,
                range_value.end_date,
            )
            total += len(expected_dates)
            not_operating_shop_days += len(dates) - len(expected_dates)
            for business_date in reversed(expected_dates):
                metric = metric_by_shop_date.get((shop_id, business_date))
                if _has_complete_daily_metrics(metric):
                    collected += 1
                    continue
                latest_state = latest_states.get((shop_id, business_date))
                missing.append(
                    OperatingDashboardCoverageMissingRead(
                        shop_id=shop_id,
                        shop_name=shop.shop_name,
                        business_date=business_date,
                        state=_coverage_state(latest_state),
                        failure_reason=_coverage_failure_reason(latest_state),
                    ),
                )
        samples = missing[:COVERAGE_MISSING_SAMPLE_LIMIT]
        return OperatingDashboardCoverageRead(
            state="available",
            supported_shop_count=len(shops),
            collected_shop_days=collected,
            total_shop_days=total,
            missing_shop_days=len(missing),
            missing_samples=samples,
            missing_samples_truncated=len(missing) > len(samples),
            manual_backfill_required=bool(missing),
            not_operating_shop_days=not_operating_shop_days,
            shops_with_unknown_operating_start=shops_with_unknown_operating_start,
            no_operating_scope=(total == 0 and not_operating_shop_days > 0),
        )

    @staticmethod
    def _shop_range_values(
        shops: list[DashboardShop],
        metric_by_shop_date: dict[tuple[UUID, date], ShopOperatingDailyMetric],
        range_value: OperatingDashboardDateRangeRead,
    ) -> dict[UUID, _ShopRangeValues]:
        values: dict[UUID, _ShopRangeValues] = {}
        for shop in shops:
            expected_dates = _expected_dates_for_shop(
                shop,
                range_value.start_date,
                range_value.end_date,
            )
            observations = [
                metric_by_shop_date.get((shop.shop_id, day)) for day in expected_dates
            ]
            # An all-pre-operation range has no expected observation.  It is
            # deliberately *not* complete coverage: the separate
            # ``not_operating_for_range`` flag tells callers why there is no
            # value, without turning it into a zero or a successful day.
            complete = bool(observations) and all(
                _has_complete_daily_metrics(observation)
                for observation in observations
            )
            collected_at = max(
                (
                    observation.collected_at
                    for observation in observations
                    if _has_complete_daily_metrics(observation)
                ),
                default=None,
            )
            valid_observations = [
                observation
                for observation in observations
                if _has_complete_daily_metrics(observation)
            ]
            valid_refund_observations = [
                observation
                for observation in observations
                if _has_available_refund_order_observation(observation)
            ]
            values[shop.shop_id] = _ShopRangeValues(
                # Keep real facts from the collected dates visible.  The
                # separate coverage flag distinguishes this partial sum from
                # a complete range; it is deliberately not a zero fallback.
                turnover_cents=(
                    sum(observation.turnover_cents for observation in valid_observations)
                    if valid_observations
                    else None
                ),
                order_count=(
                    sum(observation.order_count for observation in valid_observations)
                    if valid_observations
                    else None
                ),
                # This is a refund-time order count, not a return-piece
                # count.  Its coverage intentionally stays independent from
                # the core turnover/order observation for the same date.
                refund_order_count=(
                    sum(
                        observation.refund_order_count
                        for observation in valid_refund_observations
                    )
                    if valid_refund_observations
                    else None
                ),
                collected_at=collected_at,
                coverage_complete=complete,
                refund_order_coverage_complete=(
                    bool(observations)
                    and len(valid_refund_observations) == len(observations)
                ),
                not_operating_for_range=(
                    not expected_dates and shop.operating_start_date is not None
                ),
            )
        return values

    @staticmethod
    def _table_rows(
        shops: list[DashboardShop],
        values: dict[UUID, _ShopRangeValues],
    ) -> list[OperatingDashboardTableRowRead]:
        return [
            OperatingDashboardTableRowRead(
                shop_id=shop.shop_id,
                shop_name=shop.shop_name,
                platform=shop.platform,
                turnover_cents=values[shop.shop_id].turnover_cents,
                order_count=values[shop.shop_id].order_count,
                refund_order_count=values[shop.shop_id].refund_order_count,
                collected_at=values[shop.shop_id].collected_at,
                coverage_complete=values[shop.shop_id].coverage_complete,
                refund_order_coverage_complete=(
                    values[shop.shop_id].refund_order_coverage_complete
                ),
                not_operating_for_range=values[shop.shop_id].not_operating_for_range,
            )
            for shop in shops
        ]

    @staticmethod
    def _sort_rows(
        rows: list[OperatingDashboardTableRowRead],
        *,
        sort_field: DashboardSortField | None,
        sort_direction: DashboardSortDirection | None,
    ) -> list[OperatingDashboardTableRowRead]:
        field = sort_field or "shop_name"
        direction = sort_direction or "asc"
        value_getters = {
            "shop_name": lambda row: row.shop_name.casefold(),
            "turnover_cents": lambda row: row.turnover_cents,
            "order_count": lambda row: row.order_count,
            "refund_order_count": lambda row: row.refund_order_count,
            "collected_at": lambda row: row.collected_at,
        }
        getter = value_getters[field]
        with_values = [row for row in rows if getter(row) is not None]
        missing = [row for row in rows if getter(row) is None]
        # Keep the secondary shop_id ordering stable for both directions.
        # Python's stable sort lets the primary direction change without
        # making equal metric values randomly invert between refreshes.
        with_values.sort(key=lambda row: str(row.shop_id))
        with_values.sort(key=getter, reverse=direction == "desc")
        # Missing values remain last in both directions and use shop_id as a
        # stable deterministic tie-breaker rather than changing per refresh.
        missing.sort(key=lambda row: str(row.shop_id))
        return [*with_values, *missing]

    @staticmethod
    def _summary(
        current: dict[UUID, _ShopRangeValues],
        previous: dict[UUID, _ShopRangeValues],
        *,
        shop_count: int,
        current_core_coverage_complete: bool,
        previous_core_coverage_complete: bool,
        current_refund_coverage_complete: bool,
        previous_refund_coverage_complete: bool,
    ) -> OperatingDashboardSummaryRead:
        current_turnover = _available_sum(current.values(), "turnover_cents")
        previous_turnover = _available_sum(previous.values(), "turnover_cents")
        current_orders = _available_sum(current.values(), "order_count")
        previous_orders = _available_sum(previous.values(), "order_count")
        current_refund_orders = _available_sum(current.values(), "refund_order_count")
        previous_refund_orders = _available_sum(previous.values(), "refund_order_count")
        return OperatingDashboardSummaryRead(
            turnover_cents=current_turnover,
            order_count=current_orders,
            refund_order_count=current_refund_orders,
            refund_order_coverage_complete=current_refund_coverage_complete,
            shop_count=shop_count,
            turnover_comparison=_comparison(
                current_turnover,
                previous_turnover,
                coverage_complete=(
                    current_core_coverage_complete
                    and previous_core_coverage_complete
                ),
            ),
            order_comparison=_comparison(
                current_orders,
                previous_orders,
                coverage_complete=(
                    current_core_coverage_complete
                    and previous_core_coverage_complete
                ),
            ),
            refund_order_comparison=_comparison(
                current_refund_orders,
                previous_refund_orders,
                lower_is_better=True,
                coverage_complete=(
                    current_refund_coverage_complete
                    and previous_refund_coverage_complete
                ),
            ),
            shop_count_comparison=OperatingDashboardComparisonRead(state="unavailable"),
        )

    def _trend(
        self,
        shops: list[DashboardShop],
        metric_by_shop_date: dict[tuple[UUID, date], ShopOperatingDailyMetric],
        range_value: OperatingDashboardDateRangeRead,
    ) -> list[OperatingDashboardTrendPointRead]:
        points: list[OperatingDashboardTrendPointRead] = []
        for business_date in _calendar_days(
            range_value.start_date,
            range_value.end_date,
        ):
            operating_shops = [
                shop
                for shop in shops
                if _business_date_is_in_operating_scope(shop, business_date)
            ]
            observations = [
                metric_by_shop_date.get((shop.shop_id, business_date))
                for shop in operating_shops
            ]
            valid_observations = [
                item for item in observations if _has_complete_daily_metrics(item)
            ]
            complete = bool(observations) and len(valid_observations) == len(observations)
            turnover = (
                sum(item.turnover_cents for item in valid_observations)
                if valid_observations
                else None
            )
            orders = (
                sum(item.order_count for item in valid_observations)
                if valid_observations
                else None
            )
            points.append(
                OperatingDashboardTrendPointRead(
                    business_date=business_date,
                    turnover_cents=turnover,
                    order_count=orders,
                    coverage_complete=complete,
                ),
            )
        return points

    @staticmethod
    def _range_coverage_complete(
        shops: list[DashboardShop],
        metric_by_shop_date: dict[tuple[UUID, date], ShopOperatingDailyMetric],
        range_value: OperatingDashboardDateRangeRead,
    ) -> bool:
        """Whether every supported Shop/date in one comparison range exists.

        An empty supported scope cannot produce a reliable comparison.  This
        intentionally differs from a numerical zero, which remains a valid
        complete daily fact through ``_has_complete_daily_metrics``.
        """

        days = _calendar_days(range_value.start_date, range_value.end_date)
        return bool(shops) and all(
            _shop_has_full_comparable_range(shop, days)
            and all(
                _has_complete_daily_metrics(
                    metric_by_shop_date.get((shop.shop_id, day)),
                )
                for day in days
            )
            for shop in shops
        )

    @staticmethod
    def _refund_order_range_coverage_complete(
        shops: list[DashboardShop],
        metric_by_shop_date: dict[tuple[UUID, date], ShopOperatingDailyMetric],
        range_value: OperatingDashboardDateRangeRead,
    ) -> bool:
        """Whether every supported Shop/date has a valid refund-time count."""

        days = _calendar_days(range_value.start_date, range_value.end_date)
        return bool(shops) and all(
            _shop_has_full_comparable_range(shop, days)
            and all(
                _has_available_refund_order_observation(
                    metric_by_shop_date.get((shop.shop_id, day)),
                )
                for day in days
            )
            for shop in shops
        )

    def _require_dashboard_access(self, actor: ActorContext) -> None:
        self.module_access_service.require_module_access(actor, ModuleCode.SHOP)

    @staticmethod
    def _validate_completed_date_range(start_date: date, end_date: date) -> None:
        if end_date < start_date:
            raise OperatingDashboardInvalidRequestError("结束日期不能早于开始日期")
        if (end_date - start_date).days + 1 > 60:
            raise OperatingDashboardInvalidRequestError("日期范围最多为60个完整自然日")
        if end_date >= _shanghai_today():
            raise OperatingDashboardInvalidRequestError("经营数据只支持截至昨日的完整自然日")


def _has_complete_daily_metrics(metric: ShopOperatingDailyMetric | None) -> bool:
    """Only confirmed core metrics decide whether a Shop/date has core facts.

    `0` is a valid platform fact.  The 0040 refund observation extends the
    daily response contract but does not invalidate existing 0039 core facts.
    Its separate status decides whether a one-time refund backfill is needed.
    """

    return (
        metric is not None
        and metric.source_code == DOUYIN_CORE_INDEX_SOURCE
        and metric.metric_contract in DOUYIN_CORE_INDEX_ACCEPTED_CONTRACTS
        and metric.turnover_cents is not None
        and metric.order_count is not None
    )


def _requires_collection(metric: ShopOperatingDailyMetric | None) -> bool:
    """Whether a Shop/date needs one normal collection attempt.

    A current core gap always wins. Once the core facts are complete, only an
    `unobserved` refund field creates the finite 0040 backfill. Explicit
    unavailable/not-ready/invalid states remain visible but cannot cause a
    daily scan or repeated normal-button click to keep calling the platform.
    """

    return not _has_complete_daily_metrics(metric) or (
        metric is not None
        and metric.refund_order_status == REFUND_ORDER_STATUS_UNOBSERVED
    )


def _has_available_refund_order_observation(
    metric: ShopOperatingDailyMetric | None,
) -> bool:
    return (
        metric is not None
        and metric.source_code == DOUYIN_CORE_INDEX_SOURCE
        and metric.metric_contract in DOUYIN_CORE_INDEX_ACCEPTED_CONTRACTS
        and metric.refund_order_status == REFUND_ORDER_STATUS_AVAILABLE
        and metric.refund_order_count is not None
    )


def _refund_order_requires_attention(metric: ShopOperatingDailyMetric | None) -> bool:
    """Return true for checked optional responses that need no blind retry."""

    return (
        _has_complete_daily_metrics(metric)
        and metric is not None
        and metric.refund_order_status in REFUND_ORDER_ATTENTION_STATUSES
    )


def _latest_collection_states(
    states: Iterable[CollectionItemState],
) -> dict[tuple[UUID, date], CollectionItemState]:
    latest: dict[tuple[UUID, date], CollectionItemState] = {}
    for state in states:
        key = (state.shop_id, state.business_date)
        current = latest.get(key)
        if current is None or (state.updated_at, str(state.collection_item_id)) > (
            current.updated_at,
            str(current.collection_item_id),
        ):
            latest[key] = state
    return latest


def _latest_state(
    states: Iterable[CollectionItemState],
) -> CollectionItemState | None:
    history = list(states)
    if not history:
        return None
    return max(
        history,
        key=lambda state: (state.updated_at, str(state.collection_item_id)),
    )


def _attempts_since_last_success(states: Iterable[CollectionItemState]) -> int:
    """Count one failure chain across Jobs, not a Shop's lifetime successes."""
    attempts = 0
    for state in sorted(
        states,
        key=lambda value: (value.updated_at, str(value.collection_item_id)),
        reverse=True,
    ):
        if state.status == OperatingCollectionItemStatus.SUCCEEDED.value:
            break
        attempts += state.attempt_count
    return attempts


def _is_response_parse_failure(state: CollectionItemState) -> bool:
    return (
        state.status == OperatingCollectionItemStatus.FAILED.value
        and not state.retryable
        and state.failure_code == LEGACY_RESPONSE_PARSE_FAILURE_CODE
        and state.failure_stage == LEGACY_RESPONSE_PARSE_FAILURE_STAGE
        and state.finished_at is not None
    )


def _coverage_state(
    state: CollectionItemState | None,
) -> Literal[
    "missing",
    "collecting",
    "waiting_collection_time",
    "waiting_reauthorization",
    "failed",
    "unknown",
]:
    if state is None:
        return "missing"
    if (
        state.status == OperatingCollectionItemStatus.PENDING.value
        and state.failure_code == COLLECTION_WAITING_FOR_DAILY_BOUNDARY
    ):
        return "waiting_collection_time"
    if state.status in {
        OperatingCollectionItemStatus.PENDING.value,
        OperatingCollectionItemStatus.RUNNING.value,
    }:
        return "collecting"
    if state.status == OperatingCollectionItemStatus.PAUSED_REAUTHORIZATION.value:
        return "waiting_reauthorization"
    if state.status == OperatingCollectionItemStatus.FAILED.value:
        if state.failure_code in DOUYIN_CORE_METRIC_UNKNOWN_FAILURE_CODES:
            # The fixed platform path was observed, but it did not supply a
            # scalar for a required core metric.  This is deliberately not a
            # retryable platform failure, a numeric zero, or proof that the
            # Shop was not operating.
            return "unknown"
        return "failed"
    return "missing"


def _coverage_failure_reason(state: CollectionItemState | None) -> str | None:
    """Map a persisted failure code without disclosing raw failure details."""

    if state is None:
        return None
    if (
        state.status == OperatingCollectionItemStatus.PENDING.value
        and state.failure_code == COLLECTION_WAITING_FOR_DAILY_BOUNDARY
    ):
        return _safe_failure_message(state.failure_code)
    if state.status != OperatingCollectionItemStatus.FAILED.value:
        return None
    return _safe_failure_message(state.failure_code)


def _prioritized_collection_items(
    *,
    shops: Iterable[DashboardShop],
    start_date: date,
    end_date: date,
    business_dates: list[date] | None,
    business_dates_by_shop: dict[UUID, list[date]] | None,
) -> list[tuple[DashboardShop, date]]:
    """Order durable items yesterday-first across all Shops.

    The executor already enforces the global limit and same-Shop serialism.
    Giving every Shop's newest eligible date a lower priority than any older
    date means a long history for one Shop cannot delay another Shop's
    yesterday.  UUID ordering is only the deterministic tie-breaker.
    """

    by_shop: dict[UUID, tuple[DashboardShop, set[date]]] = {}
    fallback_dates = (
        business_dates
        if business_dates is not None
        else list(reversed(_calendar_days(start_date, end_date)))
    )
    for shop in shops:
        requested_dates = (
            business_dates_by_shop.get(shop.shop_id, [])
            if business_dates_by_shop is not None
            else fallback_dates
        )
        # Every caller, including legacy lifecycle callers that still invoke
        # ``_create_collection_job`` directly, observes a confirmed start
        # boundary.  This is a defensive final planning gate; it does not
        # infer a boundary when the date remains unknown.
        dates = {
            business_date
            for business_date in requested_dates
            if _business_date_is_in_operating_scope(shop, business_date)
        }
        by_shop[shop.shop_id] = (shop, dates)

    ordered: list[tuple[DashboardShop, date]] = []
    for business_date in sorted(
        {item_date for _, dates in by_shop.values() for item_date in dates},
        reverse=True,
    ):
        for shop_id in sorted(by_shop, key=str):
            shop, dates = by_shop[shop_id]
            if business_date in dates:
                ordered.append((shop, business_date))
    return ordered


def _calendar_days(start_date: date, end_date: date) -> list[date]:
    return [
        start_date + timedelta(days=offset)
        for offset in range((end_date - start_date).days + 1)
    ]


def _business_date_is_in_operating_scope(
    shop: DashboardShop,
    business_date: date,
) -> bool:
    """Return true unless a confirmed boundary places the date before trade."""

    return (
        shop.operating_start_date is None
        or business_date >= shop.operating_start_date
    )


def _expected_dates_for_shop(
    shop: DashboardShop,
    start_date: date,
    end_date: date,
) -> list[date]:
    """Intersect a selected range with a confirmed operating period.

    An unknown start date intentionally leaves the range untouched.  The
    caller must surface that uncertainty rather than infer a boundary from a
    first order, Shop onboarding timestamp, or a first successful request.
    """

    effective_start = start_date
    if shop.operating_start_date is not None:
        effective_start = max(effective_start, shop.operating_start_date)
    if effective_start > end_date:
        return []
    return _calendar_days(effective_start, end_date)


def _not_operating_days_in_range(
    shop: DashboardShop,
    start_date: date,
    end_date: date,
) -> int:
    return len(_calendar_days(start_date, end_date)) - len(
        _expected_dates_for_shop(shop, start_date, end_date),
    )


def _shop_has_full_comparable_range(
    shop: DashboardShop,
    days: list[date],
) -> bool:
    """A comparison cannot treat pre-operation dates as zero history."""

    return bool(days) and all(
        _business_date_is_in_operating_scope(shop, day) for day in days
    )


def _shanghai_today(now: datetime | None = None) -> date:
    resolved = now or datetime.now(SHANGHAI_TIMEZONE)
    if resolved.tzinfo is None:
        raise ValueError("now 必须包含时区")
    return resolved.astimezone(SHANGHAI_TIMEZONE).date()


def _available_sum(values: Iterable[_ShopRangeValues], field: str) -> int | None:
    """Sum only confirmed values while preserving all-missing as ``None``."""

    raw = [getattr(value, field) for value in values]
    present = [value for value in raw if value is not None]
    return sum(present) if present else None


def _comparison(
    current: int | None,
    previous: int | None,
    *,
    lower_is_better: bool = False,
    coverage_complete: bool = True,
) -> OperatingDashboardComparisonRead:
    if not coverage_complete or current is None or previous is None or previous == 0:
        return OperatingDashboardComparisonRead(state="unavailable")
    if current == previous:
        return OperatingDashboardComparisonRead(state="equal")
    increased = current > previous
    return OperatingDashboardComparisonRead(
        state="increase" if increased else "decrease",
        percentage=abs((current - previous) / previous * 100),
        favorable=(not increased if lower_is_better else increased),
    )


def _derive_job_status(items: Iterable[OperatingDataCollectionItem]) -> str:
    statuses = Counter(item.status for item in items)
    if statuses[OperatingCollectionItemStatus.RUNNING.value]:
        return OperatingCollectionJobStatus.RUNNING.value
    if (
        statuses[OperatingCollectionItemStatus.PENDING.value]
        or statuses[OperatingCollectionItemStatus.PAUSED_REAUTHORIZATION.value]
    ):
        return OperatingCollectionJobStatus.PENDING.value
    if statuses[OperatingCollectionItemStatus.FAILED.value]:
        return (
            OperatingCollectionJobStatus.PARTIAL_FAILED.value
            if statuses[OperatingCollectionItemStatus.SUCCEEDED.value]
            else OperatingCollectionJobStatus.FAILED.value
        )
    return OperatingCollectionJobStatus.SUCCEEDED.value


def _safe_failure_message(code: str | None) -> str:
    messages = {
        "SHOP_REAUTHORIZATION_REQUIRED": "店铺登录态需要重新授权",
        "SHOP_SESSION_IDENTITY_MISMATCH": "登录态与店铺身份不匹配",
        "SHOP_SESSION_VERSION_CONFLICT": "店铺登录态已更新，等待重新执行",
        "SHOP_SESSION_VALIDATION_TIMEOUT": "店铺登录态验证超时",
        "SHOP_SESSION_VALIDATION_INVALID_RESPONSE": "店铺登录态验证响应无效",
        "SHOP_SESSION_VALIDATION_FAILED": "店铺登录态验证失败",
        "DOUYIN_PLATFORM_TIMEOUT": "抖店平台请求超时",
        "DOUYIN_OPERATING_DATA_INVALID_RESPONSE": "抖店经营数据响应无效",
        "DOUYIN_OPERATING_DATA_METRICS_UNAVAILABLE": "抖店平台未提供可确认的经营指标值",
        "DOUYIN_OPERATING_DATA_METRICS_NOT_READY": "抖店经营指标暂未就绪",
        "DOUYIN_OPERATING_DATA_CORE_METRIC_MISSING": "抖店经营数据响应缺少必要指标",
        "DOUYIN_PLATFORM_REQUEST_FAILED": "抖店平台请求失败",
        "DOUYIN_OPERATING_DATA_REJECTED": "抖店平台拒绝经营数据请求",
        COLLECTION_WAITING_FOR_DAILY_BOUNDARY: "等待每日采集时间后再请求平台",
        "COLLECTION_EXECUTION_FAILED": "经营数据采集执行失败",
    }
    return messages.get(code or "", "经营数据采集失败")


def _is_running_shop_claim_conflict(error: IntegrityError) -> bool:
    """Identify only the expected PostgreSQL ownership race.

    Do not turn unrelated schema or persistence failures into an apparently
    harmless empty queue.  PostgreSQL exposes the named partial-index
    constraint through ``diag``; the text fallback supports the same named
    index in constrained test drivers.
    """

    diagnostic = getattr(error.orig, "diag", None)
    if (
        getattr(diagnostic, "constraint_name", None)
        == "uq_operating_collection_running_shop"
    ):
        return True
    return "uq_operating_collection_running_shop" in str(error.orig)
