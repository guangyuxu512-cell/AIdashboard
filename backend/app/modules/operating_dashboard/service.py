from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
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
SYSTEM_COLLECTION_KINDS = frozenset(
    {
        OperatingCollectionJobKind.INITIAL_BACKFILL.value,
        OperatingCollectionJobKind.REENABLE_BACKFILL.value,
        OperatingCollectionJobKind.DAILY.value,
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


@dataclass(frozen=True)
class _ShopRangeValues:
    turnover_cents: int | None
    order_count: int | None
    refund_order_count: int | None
    collected_at: datetime | None
    coverage_complete: bool
    refund_order_coverage_complete: bool


@dataclass(frozen=True)
class _ManualCollectionPlan:
    """One bounded, authorized update decision before any durable write."""

    business_dates_by_shop: dict[UUID, list[date]]
    active_job_ids: tuple[UUID, ...]
    missing_shop_days: int
    active_shop_days: int
    blocked_shop_days: int
    refund_attention_shop_days: int


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
    ) -> OperatingDataCollectionJobRead:
        self._require_dashboard_access(actor)
        if not self.settings.operating_dashboard_collection_execution_enabled:
            raise OperatingDashboardCollectionUnavailableError()
        self._validate_completed_date_range(request.start_date, request.end_date)
        shops = self.repository.list_authorized_shops(
            actor=actor,
            platform=request.platform,
            shop_id=request.shop_id,
        )
        # A manual refresh must always target at least one shop within the
        # actor's current authorization scope.  Reject before creating the
        # durable job so an unfiltered request cannot leave an empty orphan.
        if not shops:
            raise OperatingDashboardShopNotAvailableError()
        job = self._create_collection_job(
            kind=OperatingCollectionJobKind.MANUAL_REFRESH,
            start_date=request.start_date,
            end_date=request.end_date,
            shops=shops,
            requested_by_user_id=actor.user_id,
            requested_team_id=actor.team_id,
        )
        return self._job_read_for_actor(actor=actor, job=job)

    def request_collection_update(
        self,
        *,
        actor: ActorContext,
        request: OperatingDataCollectionRequest,
        force_recollect: bool = False,
        now: datetime | None = None,
    ) -> OperatingDataCollectionSubmissionRead:
        """Plan a normal gap-fill or an explicitly requested recollection.

        This is deliberately separate from ``enqueue_manual_collection`` so
        lifecycle callers and older explicit-retry code retain their durable
        Job contract. The dashboard button needs a truthful no-work result:
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
        if job_read is not None:
            return OperatingDataCollectionSubmissionRead(
                state="collection_queued",
                message=(
                    "已提交所选范围重新采集"
                    if force_recollect and created_job is not None
                    else "已按缺口检查采集进度"
                ),
                collection_job=job_read,
                missing_shop_days=plan.missing_shop_days,
                queued_shop_days=queued_shop_days,
                active_shop_days=plan.active_shop_days,
                blocked_shop_days=plan.blocked_shop_days,
                refund_attention_shop_days=plan.refund_attention_shop_days,
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
                refund_attention_shop_days=plan.refund_attention_shop_days,
            )
        if plan.blocked_shop_days:
            return OperatingDataCollectionSubmissionRead(
                state="attention_required",
                message="部分缺口当前不能自动补采，请查看覆盖状态并按提示处理",
                collection_job=None,
                missing_shop_days=plan.missing_shop_days,
                queued_shop_days=0,
                active_shop_days=0,
                blocked_shop_days=plan.blocked_shop_days,
                refund_attention_shop_days=plan.refund_attention_shop_days,
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
                refund_attention_shop_days=plan.refund_attention_shop_days,
            )
        return OperatingDataCollectionSubmissionRead(
            state="up_to_date",
            message="数据已是最新，无需重新采集",
            collection_job=None,
            missing_shop_days=0,
            queued_shop_days=0,
            active_shop_days=0,
            blocked_shop_days=0,
            refund_attention_shop_days=0,
        )

    def enqueue_initial_backfill_for_shop(
        self,
        *,
        shop_id: UUID,
        kind: OperatingCollectionJobKind = OperatingCollectionJobKind.INITIAL_BACKFILL,
        now: datetime | None = None,
        commit: bool = True,
    ) -> OperatingDataCollectionJob | None:
        """Compatibility name for lifecycle callers of the unified planner.

        Onboarding and re-enable paths deliberately keep their existing entry
        point and job kind.  The gap decision itself is shared with daily,
        startup, and post-reauthorization recovery below.
        """

        return self.enqueue_missing_backfill_for_shop(
            shop_id=shop_id,
            kind=kind,
            now=now,
            commit=commit,
        )

    def enqueue_missing_backfill_for_shop(
        self,
        *,
        shop_id: UUID,
        kind: OperatingCollectionJobKind,
        now: datetime | None = None,
        commit: bool = True,
    ) -> OperatingDataCollectionJob | None:
        """Persist eligible gaps for one enabled Douyin Shop.

        This method is intentionally database-only.  It neither decrypts a
        Session nor makes a platform request; the existing executor remains
        the single place that validates a stored Session immediately before
        external I/O.  Active/paused work is reused rather than duplicated.
        """

        shop = self.repository.get_shop(shop_id)
        if shop is None or shop.platform is not ShopPlatform.DOUYIN or not shop.enabled:
            return None
        resolved_now = now or datetime.now(UTC)
        end_date = _shanghai_today(resolved_now) - timedelta(days=1)
        start_date = _automatic_recovery_start(
            end_date,
            self.settings.operating_dashboard_initial_backfill_days,
        )
        dashboard_shop = DashboardShop(
            shop_id=shop.shop_id,
            shop_name=shop.display_name,
            platform=shop.platform,
            enabled=shop.enabled,
        )
        dates_by_shop = self._missing_dates_by_shop(
            shops=[dashboard_shop],
            start_date=start_date,
            end_date=end_date,
            now=resolved_now,
        )
        dates = dates_by_shop.get(shop_id, [])
        if not dates:
            return None
        return self._create_collection_job(
            kind=kind,
            start_date=start_date,
            end_date=end_date,
            shops=[dashboard_shop],
            requested_by_user_id=None,
            business_dates_by_shop=dates_by_shop,
            commit=commit,
        )

    def enqueue_daily_collection(
        self,
        *,
        business_date: date,
        now: datetime | None = None,
    ) -> OperatingDataCollectionJob:
        """Idempotently plan yesterday first, then bounded recent gaps.

        The stable daily key is a durable once-per-Shanghai-day marker.  A
        later day scans the same bounded window again, so a partial failure
        cannot suppress future eligible recovery while duplicate polling or a
        restart cannot enqueue the same daily plan twice.
        """

        dedupe_key = f"daily:{business_date.isoformat()}"
        existing = self.repository.get_job_by_dedupe_key(dedupe_key)
        if existing is not None:
            return existing
        shops = self.repository.list_enabled_douyin_shops()
        resolved_now = now or datetime.now(UTC)
        start_date = _automatic_recovery_start(
            business_date,
            self.settings.operating_dashboard_initial_backfill_days,
        )
        dates_by_shop = self._missing_dates_by_shop(
            shops=shops,
            start_date=start_date,
            end_date=business_date,
            now=resolved_now,
        )
        return self._create_collection_job(
            kind=OperatingCollectionJobKind.DAILY,
            start_date=start_date,
            end_date=business_date,
            shops=[shop for shop in shops if shop.shop_id in dates_by_shop],
            requested_by_user_id=None,
            dedupe_key=dedupe_key,
            business_dates_by_shop=dates_by_shop,
        )

    def retry_failed_collection_items(
        self,
        *,
        actor: ActorContext,
        collection_job_id: UUID,
        item_ids: Iterable[UUID],
    ) -> OperatingDataCollectionJobRead:
        self._require_dashboard_access(actor)
        source = self.repository.get_job(collection_job_id)
        if source is None:
            raise OperatingDashboardCollectionNotFoundError()
        visible_items = self.repository.list_job_items_for_actor(
            actor=actor,
            collection_job_id=collection_job_id,
        )
        if not visible_items:
            raise OperatingDashboardCollectionNotFoundError()
        requested_ids = set(item_ids)
        retryable_items = [
            item
            for item in visible_items
            if item.status == OperatingCollectionItemStatus.FAILED.value
            and item.retryable
            and (not requested_ids or item.collection_item_id in requested_ids)
        ]
        if not retryable_items:
            raise OperatingDashboardCollectionRetryUnavailableError()
        shops = self.repository.list_authorized_shops(actor=actor)
        by_id = {shop.shop_id: shop for shop in shops}
        retry_dates_by_shop: dict[UUID, list[date]] = defaultdict(list)
        for item in retryable_items:
            if item.shop_id in by_id:
                retry_dates_by_shop[item.shop_id].append(item.business_date)
        job = self._create_collection_job(
            kind=OperatingCollectionJobKind.RETRY,
            start_date=min(item.business_date for item in retryable_items),
            end_date=max(item.business_date for item in retryable_items),
            shops=[by_id[shop_id] for shop_id in retry_dates_by_shop],
            requested_by_user_id=actor.user_id,
            requested_team_id=actor.team_id,
            business_dates_by_shop=retry_dates_by_shop,
        )
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
        job_ids = self.repository.paused_job_ids_for_shop(shop_id)
        resumed = self.repository.resume_paused_reauthorization(
            shop_id=shop_id,
            now=resolved_now,
        )
        if resumed:
            self.repository.update_job_statuses(job_ids, now=resolved_now)
        # A valid login refresh resumes its original paused rows first.  The
        # shared gap planner then adds only dates that never had a durable
        # paused item (for example, dates missed while the Shop was awaiting
        # reauthorization).  Both changes commit together.
        queued = self.enqueue_missing_backfill_for_shop(
            shop_id=shop_id,
            kind=OperatingCollectionJobKind.DAILY,
            now=resolved_now,
            commit=False,
        )
        if resumed or queued is not None:
            self.session.commit()
        return resumed

    def recover_after_backend_startup(
        self,
        *,
        now: datetime | None = None,
        collection_job_id: UUID | None = None,
    ) -> OperatingDataCollectionJob:
        """Recover expired durable work, then run one bounded daily gap plan.

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
        expired = self.repository.mark_expired_running_items_pending(
            now=now,
            collection_job_id=collection_job_id,
        )
        skipped = self.repository.mark_disabled_pending_items_skipped(
            now=now,
            collection_job_id=collection_job_id,
        )
        if expired or skipped:
            self.repository.update_job_statuses(
                (*expired_job_ids, *disabled_job_ids),
                now=now,
            )

    def _missing_dates_by_shop(
        self,
        *,
        shops: Iterable[DashboardShop],
        start_date: date,
        end_date: date,
        now: datetime,
    ) -> dict[UUID, list[date]]:
        """Return automatic-recovery candidates in yesterday-first order.

        One bounded facts query and one bounded durable-item query cover the
        complete 30-day window. A real zero remains complete. Existing 0039
        facts are marked `unobserved` for the newly verified refund field and
        receive one bounded backfill; an already checked unavailable/not-ready
        /invalid optional field is not retried by every automatic scan.
        """

        selected_shops = list(shops)
        if not selected_shops:
            return {}
        shop_ids = tuple(shop.shop_id for shop in selected_shops)
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

        dates_by_shop: dict[UUID, list[date]] = {}
        for shop in selected_shops:
            missing_dates: list[date] = []
            for business_date in reversed(_calendar_days(start_date, end_date)):
                metric = metric_by_shop_date.get((shop.shop_id, business_date))
                if not _requires_collection(metric):
                    continue
                if self._automatic_gap_recovery_allowed(
                    states_by_shop_date[(shop.shop_id, business_date)],
                    now=now,
                ):
                    missing_dates.append(business_date)
            if missing_dates:
                dates_by_shop[shop.shop_id] = missing_dates
        return dates_by_shop

    def _automatic_gap_recovery_allowed(
        self,
        states: Iterable[CollectionItemState],
        *,
        now: datetime,
    ) -> bool:
        """Keep automatic recovery finite without blocking explicit manual work."""

        history = list(states)
        if any(
            state.status
            in {
                OperatingCollectionItemStatus.PENDING.value,
                OperatingCollectionItemStatus.RUNNING.value,
                OperatingCollectionItemStatus.PAUSED_REAUTHORIZATION.value,
            }
            for state in history
        ):
            # Pending/running rows own this Shop/date; paused rows must be
            # resumed after a valid login rather than recreated every day.
            return False
        if not history:
            return True
        latest = max(
            history,
            key=lambda state: (state.updated_at, str(state.collection_item_id)),
        )
        if latest.status != OperatingCollectionItemStatus.FAILED.value:
            # A historical success with no readable fact is unusual but must
            # remain repairable; skipped disabled rows must also become
            # eligible after a legitimate re-enable.
            return True
        if not latest.retryable:
            if self._approved_legacy_response_parse_recovery(latest):
                # This is intentionally a one-item Release-Gate allowlist,
                # not a broad retry policy.  Once a new attempt is created,
                # it becomes the latest state and this exception no longer
                # applies to subsequent failures.
                return True
            # Verified platform/business rejection remains visible for manual
            # handling.  A read-only background scan must not hammer it.
            return False
        cooldown = timedelta(
            seconds=self.settings.operating_dashboard_gap_recovery_retry_cooldown_seconds,
        )
        if latest.updated_at + cooldown > now:
            return False
        automatic_attempts = sum(
            state.attempt_count
            for state in history
            if state.job_kind in SYSTEM_COLLECTION_KINDS
            and state.requested_by_user_id is None
        )
        return automatic_attempts < self.settings.operating_dashboard_gap_recovery_max_attempts

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
        for an exact Release-Gate-approved legacy parser item.
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
        refund_attention_shop_days = 0
        for shop in shops:
            for business_date in reversed(_calendar_days(start_date, end_date)):
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
                if not self._manual_gap_recovery_allowed(history, now=now):
                    blocked_shop_days += 1
                    continue
                candidates[shop.shop_id].append(business_date)
        return _ManualCollectionPlan(
            business_dates_by_shop=dict(candidates),
            active_job_ids=tuple(active_job_ids),
            missing_shop_days=missing_shop_days,
            active_shop_days=active_shop_days,
            blocked_shop_days=blocked_shop_days,
            refund_attention_shop_days=refund_attention_shop_days,
        )

    def _manual_gap_recovery_allowed(
        self,
        states: Iterable[CollectionItemState],
        *,
        now: datetime,
    ) -> bool:
        """Apply the same finite safeguards to ordinary dashboard updates.

        Explicit retry remains a separate, deliberate action. Repeated clicks
        on the normal "check and fill" control must not create an unlimited
        series of attempts after a session, risk, or non-retryable failure.
        The only exception is a separately audited original item configured
        for the one-time legacy parser recovery below.
        """

        history = list(states)
        if not history:
            return True
        latest = max(
            history,
            key=lambda state: (state.updated_at, str(state.collection_item_id)),
        )
        if latest.status != OperatingCollectionItemStatus.FAILED.value:
            return True
        if not latest.retryable:
            return self._approved_legacy_response_parse_recovery(latest)
        cooldown = timedelta(
            seconds=self.settings.operating_dashboard_gap_recovery_retry_cooldown_seconds,
        )
        if latest.updated_at + cooldown > now:
            return False
        return (
            sum(state.attempt_count for state in history)
            < self.settings.operating_dashboard_collection_max_attempts
        )

    def _approved_legacy_response_parse_recovery(
        self,
        state: CollectionItemState,
    ) -> bool:
        """Allow exactly audited old parser failures to be retried once.

        The old parser incorrectly treated optional response fields as core
        requirements.  Its persisted terminal failures cannot be safely
        reclassified from a generic failure code alone, so Release Gate must
        explicitly approve each original item UUID after read-only evidence.
        A fresh item created by the ordinary planner is never on that list.
        """

        return (
            state.collection_item_id
            in self.settings.operating_dashboard_legacy_response_parse_recovery_item_ids
            and state.status == OperatingCollectionItemStatus.FAILED.value
            and not state.retryable
            and state.attempt_count == 1
            and state.failure_code == LEGACY_RESPONSE_PARSE_FAILURE_CODE
            and state.failure_stage == LEGACY_RESPONSE_PARSE_FAILURE_STAGE
            and state.finished_at is not None
        )

    def abandon_claim_if_not_executable(self, claim: CollectionClaim) -> bool:
        """Last enabled and requester-access check before external I/O."""

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
            now = datetime.now(UTC)
            self._skip_claim(
                item,
                now=now,
                failure_code="COLLECTION_REQUESTER_ACCESS_REVOKED",
                failure_message="发起更新所需的当前授权已撤销，未发起平台请求",
            )
            return True
        shop = self.repository.get_shop(claim.shop_id)
        if shop is not None and shop.enabled and shop.deleted_at is None:
            self.session.rollback()
            return False
        now = datetime.now(UTC)
        self._skip_claim(
            item,
            now=now,
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
        elif outcome.retryable and item.attempt_count < self.settings.operating_dashboard_collection_max_attempts:
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
        commit: bool = True,
    ) -> OperatingDataCollectionJob:
        # A concurrent enqueue can collide only with an active Shop/date item.
        # Retry the transaction once so the second request records explicit
        # SKIPPED rows rather than exposing a database uniqueness error.
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
                        )
                        priority += 1
                        self.repository.add_item(item)
                    self.repository.update_job_statuses(
                        (job.collection_job_id,),
                        now=datetime.now(UTC),
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
                finished_at=datetime.now(UTC),
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
                finished_at=datetime.now(UTC),
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
                finished_at=datetime.now(UTC),
            )
        return OperatingDataCollectionItem(
            collection_item_id=generate_id(),
            collection_job_id=job.collection_job_id,
            shop_id=shop.shop_id,
            business_date=business_date,
            status=OperatingCollectionItemStatus.PENDING.value,
            priority=priority,
            retryable=True,
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
            )
        latest_states = _latest_collection_states(collection_states)
        missing: list[OperatingDashboardCoverageMissingRead] = []
        collected = 0
        dates = _calendar_days(range_value.start_date, range_value.end_date)
        shop_by_id = {shop.shop_id: shop for shop in shops}
        for business_date in reversed(dates):
            for shop_id, shop in sorted(
                shop_by_id.items(),
                key=lambda item: (item[1].shop_name.casefold(), str(item[0])),
            ):
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
        automatic_start = _automatic_recovery_start(
            _shanghai_today() - timedelta(days=1),
            self.settings.operating_dashboard_initial_backfill_days,
        )
        samples = missing[:COVERAGE_MISSING_SAMPLE_LIMIT]
        return OperatingDashboardCoverageRead(
            state="available",
            supported_shop_count=len(shops),
            collected_shop_days=collected,
            total_shop_days=len(shops) * len(dates),
            missing_shop_days=len(missing),
            missing_samples=samples,
            missing_samples_truncated=len(missing) > len(samples),
            manual_backfill_required=any(
                item.business_date < automatic_start for item in missing
            ),
        )

    @staticmethod
    def _shop_range_values(
        shops: list[DashboardShop],
        metric_by_shop_date: dict[tuple[UUID, date], ShopOperatingDailyMetric],
        range_value: OperatingDashboardDateRangeRead,
    ) -> dict[UUID, _ShopRangeValues]:
        dates = _calendar_days(range_value.start_date, range_value.end_date)
        values: dict[UUID, _ShopRangeValues] = {}
        for shop in shops:
            observations = [metric_by_shop_date.get((shop.shop_id, day)) for day in dates]
            complete = all(
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
            observations = [
                metric_by_shop_date.get((shop.shop_id, business_date)) for shop in shops
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

        return bool(shops) and all(
            _has_complete_daily_metrics(metric_by_shop_date.get((shop.shop_id, day)))
            for shop in shops
            for day in _calendar_days(range_value.start_date, range_value.end_date)
        )

    @staticmethod
    def _refund_order_range_coverage_complete(
        shops: list[DashboardShop],
        metric_by_shop_date: dict[tuple[UUID, date], ShopOperatingDailyMetric],
        range_value: OperatingDashboardDateRangeRead,
    ) -> bool:
        """Whether every supported Shop/date has a valid refund-time count."""

        return bool(shops) and all(
            _has_available_refund_order_observation(
                metric_by_shop_date.get((shop.shop_id, day)),
            )
            for shop in shops
            for day in _calendar_days(range_value.start_date, range_value.end_date)
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


def _coverage_state(
    state: CollectionItemState | None,
) -> Literal["missing", "collecting", "waiting_reauthorization", "failed"]:
    if state is None:
        return "missing"
    if state.status in {
        OperatingCollectionItemStatus.PENDING.value,
        OperatingCollectionItemStatus.RUNNING.value,
    }:
        return "collecting"
    if state.status == OperatingCollectionItemStatus.PAUSED_REAUTHORIZATION.value:
        return "waiting_reauthorization"
    if state.status == OperatingCollectionItemStatus.FAILED.value:
        return "failed"
    return "missing"


def _coverage_failure_reason(state: CollectionItemState | None) -> str | None:
    """Map a persisted failure code without disclosing raw failure details."""

    if state is None or state.status != OperatingCollectionItemStatus.FAILED.value:
        return None
    return _safe_failure_message(state.failure_code)


def _automatic_recovery_start(end_date: date, days: int) -> date:
    return end_date - timedelta(days=days - 1)


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
        dates = (
            business_dates_by_shop.get(shop.shop_id, [])
            if business_dates_by_shop is not None
            else fallback_dates
        )
        by_shop[shop.shop_id] = (shop, set(dates))

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
        "DOUYIN_PLATFORM_REQUEST_FAILED": "抖店平台请求失败",
        "DOUYIN_OPERATING_DATA_REJECTED": "抖店平台拒绝经营数据请求",
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
