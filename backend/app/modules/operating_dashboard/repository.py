from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Iterable
from uuid import UUID

from sqlalchemy import case, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, aliased

from app.modules.access.contracts import ActorContext
from app.modules.access.models import TeamShopAccess
from app.modules.operating_dashboard.enums import (
    OperatingCollectionItemStatus,
    OperatingCollectionJobStatus,
    SESSION_RESTORE_DEDUPE_PREFIX,
)
from app.modules.operating_dashboard.models import (
    OperatingDataCollectionItem,
    OperatingDataCollectionJob,
    ShopOperatingDailyMetric,
)
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.models import ShopSession


@dataclass(frozen=True)
class CollectionClaim:
    collection_item_id: UUID
    collection_job_id: UUID
    shop_id: UUID
    business_date: date
    attempt_count: int
    queued_at: datetime


@dataclass(frozen=True)
class DashboardShop:
    shop_id: UUID
    shop_name: str
    platform: ShopPlatform
    enabled: bool
    # Null means the platform has not supplied a reliable opening date and no
    # authorized manager has confirmed one.  Callers must retain their full
    # selected range in that case rather than guessing from other timestamps.
    operating_start_date: date | None = None


@dataclass(frozen=True)
class CollectionItemState:
    """A bounded Shop/date history record used by automatic gap planning.

    The planner intentionally reads a finite date window in one query rather
    than issuing per-Shop or per-date history queries. It needs job ownership
    only to keep system retries bounded while leaving human-triggered retry
    available as an explicit recovery path.
    """

    collection_item_id: UUID
    collection_job_id: UUID
    shop_id: UUID
    business_date: date
    status: str
    retryable: bool
    attempt_count: int
    failure_code: str | None
    failure_stage: str | None
    finished_at: datetime | None
    updated_at: datetime
    job_kind: str
    requested_by_user_id: UUID | None


@dataclass(frozen=True)
class SessionRecoveryMetadata:
    """Only the metadata required for recovery; never read the encrypted payload."""

    shop_id: UUID
    version: int
    status: ShopSessionStatus
    captured_at: datetime | None
    validated_at: datetime | None
    identity_present: bool

    @property
    def configured(self) -> bool:
        """A recovery projection exists only when a stored Session exists."""

        return True


class OperatingDashboardRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_session_recovery_metadata(
        self, shop_ids: Iterable[UUID],
    ) -> dict[UUID, SessionRecoveryMetadata]:
        ids = tuple(set(shop_ids))
        if not ids:
            return {}
        rows = self.session.execute(
            select(
                ShopSession.shop_id, ShopSession.version, ShopSession.status,
                ShopSession.captured_at, ShopSession.validated_at,
                (Shop.platform_shop_id.is_not(None) & (Shop.platform_shop_id != "")).label("identity_present"),
            ).join(Shop, Shop.shop_id == ShopSession.shop_id).where(ShopSession.shop_id.in_(ids)),
        ).all()
        return {
            row.shop_id: SessionRecoveryMetadata(
                row.shop_id, row.version, row.status, row.captured_at,
                row.validated_at, row.identity_present,
            )
            for row in rows
        }

    def used_session_recovery_items(self, item_ids: Iterable[UUID]) -> set[UUID]:
        keys = {f"{SESSION_RESTORE_DEDUPE_PREFIX}{item_id}": item_id for item_id in item_ids}
        if not keys:
            return set()
        return {
            keys[key]
            for key in self.session.scalars(
                select(OperatingDataCollectionJob.dedupe_key).where(
                    OperatingDataCollectionJob.dedupe_key.in_(tuple(keys)),
                ),
            )
        }

    def list_authorized_shops(
        self,
        *,
        actor: ActorContext,
        platform: ShopPlatform | None = None,
        shop_id: UUID | None = None,
        include_disabled: bool = True,
    ) -> list[DashboardShop]:
        statement = self._apply_shop_scope(select(Shop), actor).where(
            Shop.deleted_at.is_(None),
        )
        if platform is not None:
            statement = statement.where(Shop.platform == platform)
        if shop_id is not None:
            statement = statement.where(Shop.shop_id == shop_id)
        if not include_disabled:
            statement = statement.where(Shop.enabled.is_(True))
        return [
            DashboardShop(
                shop_id=shop.shop_id,
                shop_name=shop.display_name,
                platform=shop.platform,
                enabled=shop.enabled,
                operating_start_date=shop.operating_start_date,
            )
            for shop in self.session.scalars(
                statement.order_by(Shop.display_name.asc(), Shop.shop_id.asc()),
            )
        ]

    def get_authorized_shop(
        self,
        *,
        actor: ActorContext,
        shop_id: UUID,
    ) -> Shop | None:
        return self.session.scalar(
            self._apply_shop_scope(select(Shop), actor).where(
                Shop.shop_id == shop_id,
                Shop.deleted_at.is_(None),
            ),
        )

    def get_shop(self, shop_id: UUID) -> Shop | None:
        return self.session.scalar(
            select(Shop).where(
                Shop.shop_id == shop_id,
                Shop.deleted_at.is_(None),
            ),
        )

    def list_metrics(
        self,
        *,
        shop_ids: Iterable[UUID],
        start_date: date,
        end_date: date,
    ) -> list[ShopOperatingDailyMetric]:
        ids = tuple(shop_ids)
        if not ids:
            return []
        return list(
            self.session.scalars(
                select(ShopOperatingDailyMetric)
                .where(
                    ShopOperatingDailyMetric.shop_id.in_(ids),
                    ShopOperatingDailyMetric.business_date >= start_date,
                    ShopOperatingDailyMetric.business_date <= end_date,
                )
                .order_by(
                    ShopOperatingDailyMetric.shop_id.asc(),
                    ShopOperatingDailyMetric.business_date.asc(),
                ),
            ),
        )

    def list_collection_item_states(
        self,
        *,
        shop_ids: Iterable[UUID],
        start_date: date,
        end_date: date,
    ) -> list[CollectionItemState]:
        """Return bounded item history for a planner/read coverage window."""

        ids = tuple(shop_ids)
        if not ids:
            return []
        rows = self.session.execute(
            select(
                OperatingDataCollectionItem.collection_item_id,
                OperatingDataCollectionItem.collection_job_id,
                OperatingDataCollectionItem.shop_id,
                OperatingDataCollectionItem.business_date,
                OperatingDataCollectionItem.status,
                OperatingDataCollectionItem.retryable,
                OperatingDataCollectionItem.attempt_count,
                OperatingDataCollectionItem.failure_code,
                OperatingDataCollectionItem.failure_stage,
                OperatingDataCollectionItem.finished_at,
                OperatingDataCollectionItem.updated_at,
                OperatingDataCollectionJob.kind,
                OperatingDataCollectionJob.requested_by_user_id,
            )
            .join(
                OperatingDataCollectionJob,
                OperatingDataCollectionJob.collection_job_id
                == OperatingDataCollectionItem.collection_job_id,
            )
            .where(
                OperatingDataCollectionItem.shop_id.in_(ids),
                OperatingDataCollectionItem.business_date >= start_date,
                OperatingDataCollectionItem.business_date <= end_date,
            )
            .order_by(
                OperatingDataCollectionItem.updated_at.asc(),
                OperatingDataCollectionItem.collection_item_id.asc(),
            ),
        ).all()
        return [
            CollectionItemState(
                collection_item_id=row.collection_item_id,
                collection_job_id=row.collection_job_id,
                shop_id=row.shop_id,
                business_date=row.business_date,
                status=row.status,
                retryable=row.retryable,
                attempt_count=row.attempt_count,
                failure_code=row.failure_code,
                failure_stage=row.failure_stage,
                finished_at=row.finished_at,
                updated_at=row.updated_at,
                job_kind=row.kind,
                requested_by_user_id=row.requested_by_user_id,
            )
            for row in rows
        ]

    def upsert_daily_metric(
        self,
        *,
        shop_id: UUID,
        business_date: date,
        source_code: str,
        metric_contract: str,
        turnover_cents: int | None,
        order_count: int | None,
        refund_order_count: int | None = None,
        refund_order_status: str = "unobserved",
        collected_at: datetime,
    ) -> None:
        statement = insert(ShopOperatingDailyMetric).values(
            shop_id=shop_id,
            business_date=business_date,
            source_code=source_code,
            metric_contract=metric_contract,
            turnover_cents=turnover_cents,
            order_count=order_count,
            refund_order_count=refund_order_count,
            refund_order_status=refund_order_status,
            collected_at=collected_at,
        )
        self.session.execute(
            statement.on_conflict_do_update(
                constraint="uq_operating_metric_shop_date",
                set_={
                    "source_code": statement.excluded.source_code,
                    "metric_contract": statement.excluded.metric_contract,
                    "turnover_cents": statement.excluded.turnover_cents,
                    "order_count": statement.excluded.order_count,
                    # An incomplete optional observation must not erase a
                    # previously confirmed nonzero/zero refund count.  The
                    # latest explicit status still tells readers not to
                    # present that retained value as a complete observation.
                    "refund_order_count": case(
                        (
                            statement.excluded.refund_order_status == "available",
                            statement.excluded.refund_order_count,
                        ),
                        else_=ShopOperatingDailyMetric.refund_order_count,
                    ),
                    "refund_order_status": statement.excluded.refund_order_status,
                    "collected_at": statement.excluded.collected_at,
                    "updated_at": datetime.now(UTC),
                },
            ),
        )

    def add_job(self, job: OperatingDataCollectionJob) -> None:
        self.session.add(job)

    def add_item(self, item: OperatingDataCollectionItem) -> None:
        self.session.add(item)

    def find_active_item(
        self,
        *,
        shop_id: UUID,
        business_date: date,
    ) -> OperatingDataCollectionItem | None:
        return self.session.scalar(
            select(OperatingDataCollectionItem).where(
                OperatingDataCollectionItem.shop_id == shop_id,
                OperatingDataCollectionItem.business_date == business_date,
                OperatingDataCollectionItem.status.in_(
                    [
                        OperatingCollectionItemStatus.PENDING.value,
                        OperatingCollectionItemStatus.RUNNING.value,
                        OperatingCollectionItemStatus.PAUSED_REAUTHORIZATION.value,
                    ],
                ),
            ),
        )

    def get_job(self, collection_job_id: UUID) -> OperatingDataCollectionJob | None:
        return self.session.get(OperatingDataCollectionJob, collection_job_id)

    def get_job_by_dedupe_key(
        self,
        dedupe_key: str,
    ) -> OperatingDataCollectionJob | None:
        return self.session.scalar(
            select(OperatingDataCollectionJob).where(
                OperatingDataCollectionJob.dedupe_key == dedupe_key,
            ),
        )

    def list_enabled_douyin_shops(self) -> list[DashboardShop]:
        return [
            DashboardShop(
                shop_id=shop.shop_id,
                shop_name=shop.display_name,
                platform=shop.platform,
                enabled=shop.enabled,
                operating_start_date=shop.operating_start_date,
            )
            for shop in self.session.scalars(
                select(Shop)
                .where(
                    Shop.platform == ShopPlatform.DOUYIN,
                    Shop.enabled.is_(True),
                    Shop.deleted_at.is_(None),
                )
                .order_by(Shop.shop_id.asc()),
            )
        ]

    def has_confirmed_metric_before(
        self,
        *,
        shop_id: UUID,
        business_date: date,
    ) -> bool:
        """Whether a proposed start date would hide a confirmed fact.

        This is intentionally broader than the current core-contract helper:
        an earlier confirmed refund observation is also evidence that the
        Shop was operating and must not be silently excluded from reads.
        """

        return self.session.scalar(
            select(ShopOperatingDailyMetric.metric_id)
            .where(
                ShopOperatingDailyMetric.shop_id == shop_id,
                ShopOperatingDailyMetric.business_date < business_date,
                or_(
                    ShopOperatingDailyMetric.turnover_cents.is_not(None),
                    ShopOperatingDailyMetric.order_count.is_not(None),
                    ShopOperatingDailyMetric.refund_order_count.is_not(None),
                ),
            )
            .limit(1),
        ) is not None

    def list_job_items(
        self,
        collection_job_id: UUID,
    ) -> list[OperatingDataCollectionItem]:
        return list(
            self.session.scalars(
                select(OperatingDataCollectionItem)
                .where(
                    OperatingDataCollectionItem.collection_job_id == collection_job_id,
                )
                .order_by(
                    OperatingDataCollectionItem.priority.asc(),
                    OperatingDataCollectionItem.created_at.asc(),
                    OperatingDataCollectionItem.collection_item_id.asc(),
                ),
            ),
        )

    def list_job_items_for_actor(
        self,
        *,
        actor: ActorContext,
        collection_job_id: UUID,
    ) -> list[OperatingDataCollectionItem]:
        statement = self._apply_shop_scope(
            select(OperatingDataCollectionItem)
            .join(Shop, Shop.shop_id == OperatingDataCollectionItem.shop_id)
            .where(
                OperatingDataCollectionItem.collection_job_id == collection_job_id,
                Shop.deleted_at.is_(None),
            ),
            actor,
        )
        return list(
            self.session.scalars(
                statement.order_by(
                    OperatingDataCollectionItem.priority.asc(),
                    OperatingDataCollectionItem.created_at.asc(),
                    OperatingDataCollectionItem.collection_item_id.asc(),
                ),
            ),
        )

    def get_item_for_update(
        self,
        *,
        collection_item_id: UUID,
    ) -> OperatingDataCollectionItem | None:
        return self.session.scalar(
            select(OperatingDataCollectionItem)
            .where(OperatingDataCollectionItem.collection_item_id == collection_item_id)
            .with_for_update(),
        )

    def mark_expired_running_items_pending(
        self,
        *,
        now: datetime,
        collection_job_id: UUID | None = None,
    ) -> int:
        conditions = [
            OperatingDataCollectionItem.status
            == OperatingCollectionItemStatus.RUNNING.value,
            OperatingDataCollectionItem.lease_until < now,
        ]
        if collection_job_id is not None:
            conditions.append(
                OperatingDataCollectionItem.collection_job_id == collection_job_id,
            )
        session_recovery = exists(select(OperatingDataCollectionJob.collection_job_id).where(
            OperatingDataCollectionJob.collection_job_id == OperatingDataCollectionItem.collection_job_id,
            OperatingDataCollectionJob.dedupe_key.startswith(SESSION_RESTORE_DEDUPE_PREFIX),
        ))
        result = self.session.execute(
            update(OperatingDataCollectionItem)
            .where(*conditions)
            .values(
                status=case((session_recovery, OperatingCollectionItemStatus.FAILED.value), else_=OperatingCollectionItemStatus.PENDING.value),
                retryable=case((session_recovery, False), else_=True),
                retry_after=case((session_recovery, None), else_=now),
                failure_code="COLLECTION_WORKER_LEASE_EXPIRED",
                failure_message=case((session_recovery, "Session恢复单次执行已中断，请人工核实"), else_="采集执行器超时后等待安全恢复"),
                failure_stage="execution",
                lease_until=None,
                started_at=None,
                finished_at=case((session_recovery, now), else_=None),
                updated_at=now,
            ),
        )
        return int(result.rowcount or 0)

    def affected_job_ids_for_expired_running_items(
        self,
        *,
        now: datetime,
        collection_job_id: UUID | None = None,
    ) -> tuple[UUID, ...]:
        conditions = [
            OperatingDataCollectionItem.status
            == OperatingCollectionItemStatus.RUNNING.value,
            OperatingDataCollectionItem.lease_until < now,
        ]
        if collection_job_id is not None:
            conditions.append(
                OperatingDataCollectionItem.collection_job_id == collection_job_id,
            )
        return tuple(
            self.session.scalars(
                select(OperatingDataCollectionItem.collection_job_id)
                .where(*conditions)
                .distinct(),
            ),
        )

    def mark_disabled_pending_items_skipped(
        self,
        *,
        now: datetime,
        collection_job_id: UUID | None = None,
    ) -> int:
        conditions = [
            OperatingDataCollectionItem.status
            == OperatingCollectionItemStatus.PENDING.value,
            exists(
                select(Shop.shop_id).where(
                    Shop.shop_id == OperatingDataCollectionItem.shop_id,
                    or_(Shop.deleted_at.is_not(None), Shop.enabled.is_(False)),
                ),
            ),
        ]
        if collection_job_id is not None:
            conditions.append(
                OperatingDataCollectionItem.collection_job_id == collection_job_id,
            )
        result = self.session.execute(
            update(OperatingDataCollectionItem)
            .where(*conditions)
            .values(
                status=OperatingCollectionItemStatus.SKIPPED.value,
                retryable=False,
                failure_code="SHOP_DISABLED",
                failure_message="店铺已停用或移除，未发起平台请求",
                failure_stage="queued",
                finished_at=now,
                updated_at=now,
            ),
        )
        return int(result.rowcount or 0)

    def affected_job_ids_for_disabled_pending_items(
        self,
        *,
        collection_job_id: UUID | None = None,
    ) -> tuple[UUID, ...]:
        conditions = [
            OperatingDataCollectionItem.status
            == OperatingCollectionItemStatus.PENDING.value,
            exists(
                select(Shop.shop_id).where(
                    Shop.shop_id == OperatingDataCollectionItem.shop_id,
                    or_(Shop.deleted_at.is_not(None), Shop.enabled.is_(False)),
                ),
            ),
        ]
        if collection_job_id is not None:
            conditions.append(
                OperatingDataCollectionItem.collection_job_id == collection_job_id,
            )
        return tuple(
            self.session.scalars(
                select(OperatingDataCollectionItem.collection_job_id)
                .where(*conditions)
                .distinct(),
            ),
        )

    def affected_job_ids_for_not_operating_items(
        self,
        *,
        shop_id: UUID | None = None,
        collection_job_id: UUID | None = None,
    ) -> tuple[UUID, ...]:
        """Find unstarted work that predates an explicit start boundary."""

        conditions = [
            OperatingDataCollectionItem.status.in_(
                [
                    OperatingCollectionItemStatus.PENDING.value,
                    OperatingCollectionItemStatus.PAUSED_REAUTHORIZATION.value,
                ],
            ),
            exists(
                select(Shop.shop_id).where(
                    Shop.shop_id == OperatingDataCollectionItem.shop_id,
                    Shop.operating_start_date.is_not(None),
                    OperatingDataCollectionItem.business_date
                    < Shop.operating_start_date,
                ),
            ),
        ]
        if shop_id is not None:
            conditions.append(OperatingDataCollectionItem.shop_id == shop_id)
        if collection_job_id is not None:
            conditions.append(
                OperatingDataCollectionItem.collection_job_id == collection_job_id,
            )
        return tuple(
            self.session.scalars(
                select(OperatingDataCollectionItem.collection_job_id)
                .where(*conditions)
                .distinct(),
            ),
        )

    def mark_not_operating_items_skipped(
        self,
        *,
        now: datetime,
        shop_id: UUID | None = None,
        collection_job_id: UUID | None = None,
    ) -> int:
        """Skip only work whose date is now outside a confirmed boundary.

        Already-running requests are not touched here.  The service performs
        one final boundary check before external I/O, so a concurrent Shop
        edit cannot turn into an unbounded request or silently delete facts.
        """

        conditions = [
            OperatingDataCollectionItem.status.in_(
                [
                    OperatingCollectionItemStatus.PENDING.value,
                    OperatingCollectionItemStatus.PAUSED_REAUTHORIZATION.value,
                ],
            ),
            exists(
                select(Shop.shop_id).where(
                    Shop.shop_id == OperatingDataCollectionItem.shop_id,
                    Shop.operating_start_date.is_not(None),
                    OperatingDataCollectionItem.business_date
                    < Shop.operating_start_date,
                ),
            ),
        ]
        if shop_id is not None:
            conditions.append(OperatingDataCollectionItem.shop_id == shop_id)
        if collection_job_id is not None:
            conditions.append(
                OperatingDataCollectionItem.collection_job_id == collection_job_id,
            )
        result = self.session.execute(
            update(OperatingDataCollectionItem)
            .where(*conditions)
            .values(
                status=OperatingCollectionItemStatus.SKIPPED.value,
                retryable=False,
                retry_after=None,
                failure_code="SHOP_NOT_OPERATING_ON_DATE",
                failure_message="该业务日期早于已确认经营起算日，未发起平台请求",
                failure_stage="queued",
                lease_until=None,
                finished_at=now,
                updated_at=now,
            ),
        )
        return int(result.rowcount or 0)

    def acquire_global_claim_lock(self) -> None:
        """Serialize the short claim transaction across PostgreSQL processes.

        The durable item rows already prevent duplicate Shop/date work.  A
        separate transaction-scoped advisory lock is needed before counting
        running items, otherwise several Backend processes can each observe
        spare capacity and collectively exceed the configured global limit.
        It is deliberately released at commit/rollback, before platform I/O.

        SQLite is not a production execution store; keeping it a no-op lets
        narrow non-PostgreSQL unit fixtures exercise service behavior without
        pretending to provide the production cross-process guarantee.
        """

        if self.session.get_bind().dialect.name != "postgresql":
            return
        self.session.execute(
            select(
                func.pg_advisory_xact_lock(
                    6_317_189_432_001,
                ),
            ),
        )

    def count_running_items(self) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(OperatingDataCollectionItem)
                .where(
                    OperatingDataCollectionItem.status
                    == OperatingCollectionItemStatus.RUNNING.value,
                ),
            )
            or 0,
        )

    def claim_next(
        self,
        *,
        now: datetime,
        lease_until: datetime,
        collection_job_id: UUID | None = None,
    ) -> CollectionClaim | None:
        """Claim one due item after all database-only eligibility checks.

        The partial unique running-Shop index is the final cross-process guard;
        this query also observes it before attempting the state transition.
        """

        # SQLAlchemy needs an alias to correlate the self EXISTS correctly.
        running = aliased(OperatingDataCollectionItem)
        no_running_for_shop = ~exists(
            select(running.collection_item_id).where(
                running.shop_id == OperatingDataCollectionItem.shop_id,
                running.status == OperatingCollectionItemStatus.RUNNING.value,
            ),
        )
        conditions = [
            OperatingDataCollectionItem.status
            == OperatingCollectionItemStatus.PENDING.value,
            or_(
                OperatingDataCollectionItem.retry_after.is_(None),
                OperatingDataCollectionItem.retry_after <= now,
            ),
            Shop.enabled.is_(True),
            Shop.deleted_at.is_(None),
            or_(
                Shop.operating_start_date.is_(None),
                OperatingDataCollectionItem.business_date >= Shop.operating_start_date,
            ),
            no_running_for_shop,
        ]
        if collection_job_id is not None:
            conditions.append(
                OperatingDataCollectionItem.collection_job_id == collection_job_id,
            )
        candidate = self.session.scalar(
            select(OperatingDataCollectionItem)
            .join(Shop, Shop.shop_id == OperatingDataCollectionItem.shop_id)
            .where(*conditions)
            .order_by(
                OperatingDataCollectionItem.priority.asc(),
                OperatingDataCollectionItem.created_at.asc(),
                OperatingDataCollectionItem.collection_item_id.asc(),
            )
            .with_for_update(skip_locked=True)
            .limit(1),
        )
        if candidate is None:
            return None
        candidate.status = OperatingCollectionItemStatus.RUNNING.value
        candidate.attempt_count += 1
        candidate.retryable = False
        candidate.retry_after = None
        candidate.lease_until = lease_until
        candidate.started_at = now
        candidate.finished_at = None
        candidate.failure_code = None
        candidate.failure_message = None
        candidate.failure_stage = None
        candidate.updated_at = now
        self._sync_job_status(candidate.collection_job_id, now=now)
        self.session.flush()
        return CollectionClaim(
            collection_item_id=candidate.collection_item_id,
            collection_job_id=candidate.collection_job_id,
            shop_id=candidate.shop_id,
            business_date=candidate.business_date,
            attempt_count=candidate.attempt_count,
            queued_at=candidate.created_at,
        )

    def pause_pending_for_reauthorization(
        self,
        *,
        shop_id: UUID,
        now: datetime,
        failure_code: str,
    ) -> tuple[UUID, ...]:
        """Pause all not-yet-dispatched dates for a Shop after auth failure."""

        job_ids = tuple(
            self.session.scalars(
                select(OperatingDataCollectionItem.collection_job_id)
                .where(
                    OperatingDataCollectionItem.shop_id == shop_id,
                    OperatingDataCollectionItem.status
                    == OperatingCollectionItemStatus.PENDING.value,
                )
                .distinct(),
            ),
        )
        if not job_ids:
            return ()
        self.session.execute(
            update(OperatingDataCollectionItem)
            .where(
                OperatingDataCollectionItem.shop_id == shop_id,
                OperatingDataCollectionItem.status
                == OperatingCollectionItemStatus.PENDING.value,
            )
            .values(
                status=OperatingCollectionItemStatus.PAUSED_REAUTHORIZATION.value,
                retryable=False,
                retry_after=None,
                failure_code=failure_code,
                failure_message="店铺登录态需要重新授权",
                failure_stage="session_preparation",
                lease_until=None,
                finished_at=now,
                updated_at=now,
            ),
        )
        return job_ids

    def resume_paused_reauthorization(
        self,
        *,
        shop_id: UUID,
        now: datetime,
    ) -> int:
        result = self.session.execute(
            update(OperatingDataCollectionItem)
            .where(
                OperatingDataCollectionItem.shop_id == shop_id,
                OperatingDataCollectionItem.status
                == OperatingCollectionItemStatus.PAUSED_REAUTHORIZATION.value,
            )
            .values(
                status=OperatingCollectionItemStatus.PENDING.value,
                retryable=True,
                retry_after=now,
                failure_code=None,
                failure_message=None,
                failure_stage=None,
                updated_at=now,
            ),
        )
        return int(result.rowcount or 0)

    def defer_pending_items_until(
        self,
        *,
        business_date: date,
        available_at: datetime,
        now: datetime,
        shop_id: UUID | None = None,
        collection_job_id: UUID | None = None,
    ) -> tuple[UUID, ...]:
        """Keep already-queued prior-day work out of the platform before due.

        This is deliberately a narrow persistence primitive: Service owns the
        Shanghai eligibility rule, while the repository only delays matching
        pending rows.  It also protects rows created by an older process
        before the shared planner was deployed.
        """

        conditions = [
            OperatingDataCollectionItem.status
            == OperatingCollectionItemStatus.PENDING.value,
            OperatingDataCollectionItem.business_date == business_date,
            or_(
                OperatingDataCollectionItem.retry_after.is_(None),
                OperatingDataCollectionItem.retry_after < available_at,
            ),
        ]
        if shop_id is not None:
            conditions.append(OperatingDataCollectionItem.shop_id == shop_id)
        if collection_job_id is not None:
            conditions.append(
                OperatingDataCollectionItem.collection_job_id == collection_job_id,
            )
        job_ids = tuple(
            self.session.scalars(
                select(OperatingDataCollectionItem.collection_job_id)
                .where(*conditions)
                .distinct(),
            ),
        )
        if not job_ids:
            return ()
        self.session.execute(
            update(OperatingDataCollectionItem)
            .where(*conditions)
            .values(
                retryable=True,
                retry_after=available_at,
                failure_code="COLLECTION_WAITING_FOR_DAILY_BOUNDARY",
                failure_message="等待每日采集时间后再请求平台",
                failure_stage="queued",
                lease_until=None,
                updated_at=now,
            ),
        )
        return job_ids

    def paused_job_ids_for_shop(self, shop_id: UUID) -> tuple[UUID, ...]:
        return tuple(
            self.session.scalars(
                select(OperatingDataCollectionItem.collection_job_id)
                .where(
                    OperatingDataCollectionItem.shop_id == shop_id,
                    OperatingDataCollectionItem.status
                    == OperatingCollectionItemStatus.PAUSED_REAUTHORIZATION.value,
                )
                .distinct(),
            ),
        )

    def pending_or_running_job_ids(self) -> tuple[UUID, ...]:
        return tuple(
            self.session.scalars(
                select(OperatingDataCollectionItem.collection_job_id)
                .where(
                    OperatingDataCollectionItem.status.in_(
                        [
                            OperatingCollectionItemStatus.PENDING.value,
                            OperatingCollectionItemStatus.RUNNING.value,
                        ],
                    ),
                )
                .distinct(),
            ),
        )

    def update_job_statuses(self, job_ids: Iterable[UUID], *, now: datetime) -> None:
        for job_id in set(job_ids):
            self._sync_job_status(job_id, now=now)

    def _sync_job_status(self, collection_job_id: UUID, *, now: datetime) -> None:
        job = self.session.get(OperatingDataCollectionJob, collection_job_id)
        if job is None:
            return
        statuses = Counter(
            self.session.scalars(
                select(OperatingDataCollectionItem.status).where(
                    OperatingDataCollectionItem.collection_job_id == collection_job_id,
                ),
            ),
        )
        if statuses.get(OperatingCollectionItemStatus.RUNNING.value, 0):
            status = OperatingCollectionJobStatus.RUNNING.value
            finished_at = None
            started_at = job.started_at or now
        elif statuses.get(OperatingCollectionItemStatus.PENDING.value, 0) or statuses.get(
            OperatingCollectionItemStatus.PAUSED_REAUTHORIZATION.value,
            0,
        ):
            status = OperatingCollectionJobStatus.PENDING.value
            finished_at = None
            started_at = job.started_at
        elif statuses.get(OperatingCollectionItemStatus.FAILED.value, 0):
            status = (
                OperatingCollectionJobStatus.PARTIAL_FAILED.value
                if statuses.get(OperatingCollectionItemStatus.SUCCEEDED.value, 0)
                else OperatingCollectionJobStatus.FAILED.value
            )
            finished_at = now
            started_at = job.started_at or now
        else:
            status = OperatingCollectionJobStatus.SUCCEEDED.value
            finished_at = now
            started_at = job.started_at or now
        job.status = status
        job.started_at = started_at
        job.finished_at = finished_at
        job.updated_at = now

    @staticmethod
    def _apply_shop_scope(statement, actor: ActorContext):
        if actor.is_super_account:
            return statement
        return statement.where(
            exists(
                select(TeamShopAccess.team_id).where(
                    TeamShopAccess.team_id == actor.require_team_id(),
                    TeamShopAccess.shop_id == Shop.shop_id,
                ),
            ),
        )
