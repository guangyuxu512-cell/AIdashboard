from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from threading import Barrier, Lock, Thread
from time import sleep
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.models import (
    Team,
    TeamMembership,
    TeamModuleAccess,
    TeamShopAccess,
)
from app.modules.access.module_access import ModuleCode
from app.modules.operating_dashboard.enums import OperatingCollectionItemStatus
from app.modules.operating_dashboard.exceptions import (
    OperatingDashboardCollectionUnavailableError,
)
from app.modules.operating_dashboard.executor import OperatingDataCollectionExecutor
from app.modules.operating_dashboard.models import (
    OperatingDataCollectionItem,
    OperatingDataCollectionJob,
    ShopOperatingDailyMetric,
)
from app.modules.operating_dashboard.service import OperatingDashboardService
from app.modules.operating_dashboard.schemas import OperatingDataCollectionRequest
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.shops.schemas import ShopUpdate
from app.modules.shops.service import ShopService
from app.modules.users.models import User
from app.platforms.douyin.operating_data import CompassDailyMetrics
from app.platforms.douyin.operating_data_executor import (
    CollectionOutcome,
    CollectionStage,
    CollectionStatus,
    CollectionTimings,
    DailyCollectionRequest,
)
from app.shared.pagination import PaginationParams


pytestmark = pytest.mark.integration

DAY_ONE = date(2026, 9, 18)
DAY_TWO = date(2026, 9, 19)


class _ModuleAccessStub:
    def require_module_access(self, actor: ActorContext, module_code: object) -> None:
        del actor, module_code


def _settings(**values: object) -> Settings:
    defaults: dict[str, object] = {
        "operating_dashboard_collection_execution_enabled": True,
        "operating_dashboard_collection_scan_interval_seconds": 1,
        "operating_dashboard_collection_lease_seconds": 60,
        "operating_dashboard_collection_max_attempts": 2,
        "operating_dashboard_collection_retry_base_seconds": 1,
        "operating_dashboard_initial_backfill_days": 30,
        "douyin_compass_collection_concurrency": 5,
    }
    return Settings(_env_file=None, **(defaults | values))


def _actor(*, user_id: UUID, team_id: UUID | None, super_account: bool) -> ActorContext:
    return ActorContext(
        user_id=user_id,
        user_display_name="Operating dashboard test actor",
        team_id=team_id,
        membership_id=None,
        role_code="super_account" if super_account else "member",
        data_scope=DataScope.ALL if super_account else DataScope.TEAM,
        is_super_account=super_account,
    )


def _service(session: Session, **settings: object) -> OperatingDashboardService:
    return OperatingDashboardService(
        session,
        module_access_service=_ModuleAccessStub(),  # type: ignore[arg-type]
        settings=_settings(**settings),
    )


def _grant_dashboard_execution_access(
    session: Session,
    *,
    user_id: UUID,
    team_id: UUID,
) -> None:
    session.add_all(
        [
            TeamMembership(team_id=team_id, user_id=user_id, enabled=True),
            TeamModuleAccess(team_id=team_id, module_code=ModuleCode.SHOP.value),
        ],
    )


def _cleanup(engine: Engine, ids: set[UUID]) -> None:
    with Session(engine) as session:
        job_ids = session.scalars(
            select(OperatingDataCollectionItem.collection_job_id).where(
                OperatingDataCollectionItem.shop_id.in_(ids),
            ),
        ).all()
        session.execute(
            delete(OperatingDataCollectionItem).where(
                OperatingDataCollectionItem.shop_id.in_(ids),
            ),
        )
        if job_ids:
            session.execute(
                delete(OperatingDataCollectionJob).where(
                    OperatingDataCollectionJob.collection_job_id.in_(job_ids),
                ),
            )
        session.execute(
            delete(ShopOperatingDailyMetric).where(
                ShopOperatingDailyMetric.shop_id.in_(ids),
            ),
        )
        session.execute(delete(TeamShopAccess).where(TeamShopAccess.shop_id.in_(ids)))
        session.execute(delete(Shop).where(Shop.shop_id.in_(ids)))
        session.commit()


def _seed_shop(
    session: Session,
    *,
    display_name: str,
    enabled: bool = True,
    platform: ShopPlatform = ShopPlatform.DOUYIN,
) -> Shop:
    shop = Shop(
        shop_id=uuid4(),
        display_name=display_name,
        platform=platform,
        platform_shop_id=f"fixture-{uuid4().hex}",
        enabled=enabled,
    )
    session.add(shop)
    return shop


def _success(
    request: DailyCollectionRequest,
    *,
    turnover: int = 100,
    orders: int = 2,
) -> CollectionOutcome:
    return CollectionOutcome(
        request=request,
        status=CollectionStatus.SUCCEEDED,
        stage=CollectionStage.COMPLETE,
        retryable=False,
        requires_reauthorization=False,
        metrics=CompassDailyMetrics(turnover, orders, 0, 0, 0),
        timings=CollectionTimings(
            session_preparation_ms=1,
            signature_ms=2,
            platform_response_ms=3,
            response_parse_ms=4,
            total_ms=10,
        ),
    )


def test_postgresql_dashboard_scope_sort_and_idempotent_metric_update(
    postgresql_engine: Engine,
) -> None:
    user_id = uuid4()
    team_id = uuid4()
    other_team_id = uuid4()
    shops: set[UUID] = set()
    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    User(user_id=user_id, display_name="Dashboard test user"),
                    Team(team_id=team_id, name="Dashboard A"),
                    Team(team_id=other_team_id, name="Dashboard B"),
                ],
            )
            alpha = _seed_shop(session, display_name="Alpha 店铺")
            beta = _seed_shop(session, display_name="中文店铺")
            missing = _seed_shop(session, display_name="Missing 店铺")
            hidden = _seed_shop(session, display_name="Hidden 店铺")
            session.flush()
            shops.update(
                {alpha.shop_id, beta.shop_id, missing.shop_id, hidden.shop_id},
            )
            session.add_all(
                [
                    TeamShopAccess(team_id=team_id, shop_id=alpha.shop_id),
                    TeamShopAccess(team_id=team_id, shop_id=beta.shop_id),
                    TeamShopAccess(team_id=team_id, shop_id=missing.shop_id),
                    TeamShopAccess(team_id=other_team_id, shop_id=hidden.shop_id),
                ],
            )
            repository = _service(session).repository
            for shop, amount, orders in ((alpha, 100, 1), (beta, 400, 4), (hidden, 999, 9)):
                for business_day in (DAY_ONE, DAY_TWO):
                    repository.upsert_daily_metric(
                        shop_id=shop.shop_id,
                        business_date=business_day,
                        source_code="test",
                        metric_contract="test-v1",
                        turnover_cents=amount,
                        order_count=orders,
                        collected_at=datetime(2026, 9, 20, tzinfo=UTC),
                    )
            # Recollection updates exactly the one daily fact rather than
            # accumulating a duplicate observation.
            repository.upsert_daily_metric(
                shop_id=alpha.shop_id,
                business_date=DAY_TWO,
                source_code="test",
                metric_contract="test-v1",
                turnover_cents=300,
                order_count=3,
                collected_at=datetime(2026, 9, 20, 1, tzinfo=UTC),
            )
            session.commit()

            result = _service(session).read(
                actor=_actor(user_id=user_id, team_id=team_id, super_account=False),
                start_date=DAY_ONE,
                end_date=DAY_TWO,
                platform=None,
                shop_id=None,
                sort_field="turnover_cents",
                sort_direction="desc",
                pagination=PaginationParams(page=1, page_size=2),
            )

            assert result.table.total == 3
            assert [row.shop_id for row in result.table.items] == [beta.shop_id, alpha.shop_id]
            assert result.table.items[1].turnover_cents == 400
            assert result.table.items[0].return_quantity is None
            assert result.summary.turnover_cents is None
            assert result.summary.order_count is None
            assert all(option.shop_id != hidden.shop_id for option in result.all_available_shops)

            page_two = _service(session).read(
                actor=_actor(user_id=user_id, team_id=team_id, super_account=False),
                start_date=DAY_ONE,
                end_date=DAY_TWO,
                platform=None,
                shop_id=None,
                sort_field="turnover_cents",
                sort_direction="desc",
                pagination=PaginationParams(page=2, page_size=2),
            )
            assert [row.shop_id for row in page_two.table.items] == [missing.shop_id]
            assert page_two.table.items[0].turnover_cents is None
    finally:
        _cleanup(postgresql_engine, shops)
        with Session(postgresql_engine) as session:
            session.execute(delete(Team).where(Team.team_id.in_([team_id, other_team_id])))
            session.execute(delete(User).where(User.user_id == user_id))
            session.commit()


def test_postgresql_durable_executor_limits_concurrency_and_respects_disabled_shop(
    postgresql_engine: Engine,
) -> None:
    user_id = uuid4()
    team_id = uuid4()
    shops: set[UUID] = set()
    active = 0
    highest_active = 0
    active_per_shop: defaultdict[UUID, int] = defaultdict(int)
    highest_per_shop: defaultdict[UUID, int] = defaultdict(int)
    calls: list[DailyCollectionRequest] = []
    lock = Lock()
    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    User(user_id=user_id, display_name="Executor test user"),
                    Team(team_id=team_id, name="Executor team"),
                ],
            )
            session.flush()
            _grant_dashboard_execution_access(
                session,
                user_id=user_id,
                team_id=team_id,
            )
            seeded = [_seed_shop(session, display_name=f"采集店铺 {index}") for index in range(5)]
            disabled = _seed_shop(session, display_name="已停用店铺", enabled=True)
            session.flush()
            shops.update(shop.shop_id for shop in [*seeded, disabled])
            session.add_all(
                [TeamShopAccess(team_id=team_id, shop_id=shop.shop_id) for shop in seeded]
                + [TeamShopAccess(team_id=team_id, shop_id=disabled.shop_id)],
            )
            session.commit()

            actor = _actor(user_id=user_id, team_id=team_id, super_account=False)
            job = _service(session).enqueue_manual_collection(
                actor=actor,
                request=OperatingDataCollectionRequest(
                    start_date=DAY_ONE,
                    end_date=DAY_TWO,
                ),
            )
            # Disable after queuing.  The executor must record a skip without
            # invoking the external collector for this Shop.
            disabled.enabled = False
            session.commit()

        def collector(request: DailyCollectionRequest) -> CollectionOutcome:
            nonlocal active, highest_active
            with lock:
                active += 1
                active_per_shop[request.shop_id] += 1
                highest_active = max(highest_active, active)
                highest_per_shop[request.shop_id] = max(
                    highest_per_shop[request.shop_id],
                    active_per_shop[request.shop_id],
                )
                calls.append(request)
            sleep(0.02)
            with lock:
                active -= 1
                active_per_shop[request.shop_id] -= 1
            return _success(request, turnover=100 + len(calls), orders=2)

        settings = _settings(douyin_compass_collection_concurrency=5)
        executor = OperatingDataCollectionExecutor(
            session_factory=lambda: Session(postgresql_engine, expire_on_commit=False),
            collector=collector,
            settings=settings,
        )
        while executor.execute_available():
            pass

        assert highest_active <= 5
        assert all(value <= 1 for value in highest_per_shop.values())
        assert disabled.shop_id not in {request.shop_id for request in calls}

        with Session(postgresql_engine) as session:
            items = session.scalars(
                select(OperatingDataCollectionItem).where(
                    OperatingDataCollectionItem.collection_job_id == job.collection_job_id,
                ),
            ).all()
            assert sum(item.status == OperatingCollectionItemStatus.SKIPPED.value for item in items) == 2
            assert sum(item.status == OperatingCollectionItemStatus.SUCCEEDED.value for item in items) == 10
            assert all(
                item.queue_wait_ms is not None and item.total_ms is not None
                for item in items
                if item.status == OperatingCollectionItemStatus.SUCCEEDED.value
            )
            assert session.scalar(
                select(ShopOperatingDailyMetric).where(
                    ShopOperatingDailyMetric.shop_id == seeded[0].shop_id,
                    ShopOperatingDailyMetric.business_date == DAY_ONE,
                ),
            ) is not None
    finally:
        _cleanup(postgresql_engine, shops)
        with Session(postgresql_engine) as session:
            session.execute(
                delete(TeamModuleAccess).where(TeamModuleAccess.team_id == team_id),
            )
            session.execute(
                delete(TeamMembership).where(TeamMembership.team_id == team_id),
            )
            session.execute(delete(Team).where(Team.team_id == team_id))
            session.execute(delete(User).where(User.user_id == user_id))
            session.commit()


def test_postgresql_reauthorization_pauses_remaining_dates_and_resume_is_explicit(
    postgresql_engine: Engine,
) -> None:
    user_id = uuid4()
    team_id = uuid4()
    shops: set[UUID] = set()
    calls: list[DailyCollectionRequest] = []
    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    User(user_id=user_id, display_name="Reauthorization user"),
                    Team(team_id=team_id, name="Reauthorization team"),
                ],
            )
            session.flush()
            _grant_dashboard_execution_access(
                session,
                user_id=user_id,
                team_id=team_id,
            )
            shop = _seed_shop(session, display_name="需要重登店铺")
            session.flush()
            shops.add(shop.shop_id)
            session.add(TeamShopAccess(team_id=team_id, shop_id=shop.shop_id))
            session.commit()
            job = _service(session).enqueue_manual_collection(
                actor=_actor(user_id=user_id, team_id=team_id, super_account=False),
                request=OperatingDataCollectionRequest(
                    start_date=DAY_ONE,
                    end_date=DAY_TWO,
                ),
            )

        first = True

        def collector(request: DailyCollectionRequest) -> CollectionOutcome:
            nonlocal first
            calls.append(request)
            if first:
                first = False
                return CollectionOutcome(
                    request=request,
                    status=CollectionStatus.FAILED,
                    stage=CollectionStage.SESSION_PREPARATION,
                    retryable=False,
                    requires_reauthorization=True,
                    failure_code="SHOP_REAUTHORIZATION_REQUIRED",
                    timings=CollectionTimings(total_ms=1),
                )
            return _success(request)

        executor = OperatingDataCollectionExecutor(
            session_factory=lambda: Session(postgresql_engine, expire_on_commit=False),
            collector=collector,
            settings=_settings(douyin_compass_collection_concurrency=5),
        )
        assert executor.execute_available() == 1
        with Session(postgresql_engine, expire_on_commit=False) as session:
            items = session.scalars(
                select(OperatingDataCollectionItem)
                .where(OperatingDataCollectionItem.collection_job_id == job.collection_job_id)
                .order_by(OperatingDataCollectionItem.priority),
            ).all()
            assert all(
                item.status == OperatingCollectionItemStatus.PAUSED_REAUTHORIZATION.value
                for item in items
            )
            assert _service(session).resume_after_session_refresh(shop.shop_id) == 2

        assert executor.execute_available() == 1
        assert len(calls) == 2
    finally:
        _cleanup(postgresql_engine, shops)
        with Session(postgresql_engine) as session:
            session.execute(
                delete(TeamModuleAccess).where(TeamModuleAccess.team_id == team_id),
            )
            session.execute(
                delete(TeamMembership).where(TeamMembership.team_id == team_id),
            )
            session.execute(delete(Team).where(Team.team_id == team_id))
            session.execute(delete(User).where(User.user_id == user_id))
            session.commit()


def test_postgresql_executor_rechecks_manual_requester_shop_access(
    postgresql_engine: Engine,
) -> None:
    """An access revocation after enqueue prevents the platform call."""

    user_id = uuid4()
    team_id = uuid4()
    shops: set[UUID] = set()
    calls: list[DailyCollectionRequest] = []
    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    User(user_id=user_id, display_name="Revoked requester user"),
                    Team(team_id=team_id, name="Revoked requester team"),
                ],
            )
            session.flush()
            _grant_dashboard_execution_access(
                session,
                user_id=user_id,
                team_id=team_id,
            )
            shop = _seed_shop(session, display_name="撤权前请求店铺")
            session.flush()
            shops.add(shop.shop_id)
            session.add(TeamShopAccess(team_id=team_id, shop_id=shop.shop_id))
            session.commit()
            job = _service(session).enqueue_manual_collection(
                actor=_actor(user_id=user_id, team_id=team_id, super_account=False),
                request=OperatingDataCollectionRequest(
                    start_date=DAY_ONE,
                    end_date=DAY_ONE,
                    shop_id=shop.shop_id,
                ),
            )
            session.execute(
                delete(TeamShopAccess).where(
                    TeamShopAccess.team_id == team_id,
                    TeamShopAccess.shop_id == shop.shop_id,
                ),
            )
            session.commit()

        def collector(request: DailyCollectionRequest) -> CollectionOutcome:
            calls.append(request)
            return _success(request)

        executor = OperatingDataCollectionExecutor(
            session_factory=lambda: Session(postgresql_engine, expire_on_commit=False),
            collector=collector,
            settings=_settings(),
        )
        assert executor.execute_available() == 1
        assert calls == []

        with Session(postgresql_engine) as session:
            item = session.scalar(
                select(OperatingDataCollectionItem).where(
                    OperatingDataCollectionItem.collection_job_id == job.collection_job_id,
                ),
            )
            assert item is not None
            assert item.status == OperatingCollectionItemStatus.SKIPPED.value
            assert item.failure_code == "COLLECTION_REQUESTER_ACCESS_REVOKED"
    finally:
        _cleanup(postgresql_engine, shops)
        with Session(postgresql_engine) as session:
            session.execute(
                delete(TeamModuleAccess).where(TeamModuleAccess.team_id == team_id),
            )
            session.execute(
                delete(TeamMembership).where(TeamMembership.team_id == team_id),
            )
            session.execute(delete(Team).where(Team.team_id == team_id))
            session.execute(delete(User).where(User.user_id == user_id))
            session.commit()


def test_postgresql_rejects_manual_collection_when_execution_is_disabled(
    postgresql_engine: Engine,
) -> None:
    user_id = uuid4()
    team_id = uuid4()
    shops: set[UUID] = set()
    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    User(user_id=user_id, display_name="Unavailable collection user"),
                    Team(team_id=team_id, name="Unavailable collection team"),
                ],
            )
            shop = _seed_shop(session, display_name="不可执行采集店铺")
            session.flush()
            shops.add(shop.shop_id)
            session.add(TeamShopAccess(team_id=team_id, shop_id=shop.shop_id))
            session.commit()

            with pytest.raises(OperatingDashboardCollectionUnavailableError):
                _service(
                    session,
                    operating_dashboard_collection_execution_enabled=False,
                ).enqueue_manual_collection(
                    actor=_actor(
                        user_id=user_id,
                        team_id=team_id,
                        super_account=False,
                    ),
                    request=OperatingDataCollectionRequest(
                        start_date=DAY_ONE,
                        end_date=DAY_ONE,
                    ),
                )

            assert (
                session.scalar(
                    select(OperatingDataCollectionJob).where(
                        OperatingDataCollectionJob.requested_by_user_id == user_id,
                    ),
                )
                is None
            )
    finally:
        _cleanup(postgresql_engine, shops)
        with Session(postgresql_engine) as session:
            session.execute(delete(Team).where(Team.team_id == team_id))
            session.execute(delete(User).where(User.user_id == user_id))
            session.commit()


def test_postgresql_concurrent_enqueue_creates_one_active_shop_date_claim(
    postgresql_engine: Engine,
) -> None:
    """Separate Sessions model distinct Backend processes sharing PostgreSQL."""

    user_id = uuid4()
    team_id = uuid4()
    shops: set[UUID] = set()
    barrier = Barrier(2)
    jobs = []
    errors: list[Exception] = []
    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    User(user_id=user_id, display_name="Concurrent enqueue user"),
                    Team(team_id=team_id, name="Concurrent enqueue team"),
                ],
            )
            shop = _seed_shop(session, display_name="跨进程互斥店铺")
            session.flush()
            shops.add(shop.shop_id)
            session.add(TeamShopAccess(team_id=team_id, shop_id=shop.shop_id))
            session.commit()

        actor = _actor(user_id=user_id, team_id=team_id, super_account=False)

        def enqueue_from_independent_session() -> None:
            try:
                with Session(postgresql_engine, expire_on_commit=False) as session:
                    barrier.wait(timeout=5)
                    job = _service(session).enqueue_manual_collection(
                        actor=actor,
                        request=OperatingDataCollectionRequest(
                            start_date=DAY_ONE,
                            end_date=DAY_ONE,
                            shop_id=shop.shop_id,
                        ),
                    )
                    jobs.append(job)
            except Exception as error:  # pragma: no cover - assertion below
                errors.append(error)

        first = Thread(target=enqueue_from_independent_session)
        second = Thread(target=enqueue_from_independent_session)
        first.start()
        second.start()
        first.join(timeout=15)
        second.join(timeout=15)

        assert not first.is_alive()
        assert not second.is_alive()
        assert errors == []
        assert len(jobs) == 2

        with Session(postgresql_engine) as session:
            items = session.scalars(
                select(OperatingDataCollectionItem).where(
                    OperatingDataCollectionItem.shop_id == shop.shop_id,
                    OperatingDataCollectionItem.business_date == DAY_ONE,
                ),
            ).all()
            assert len(items) == 2
            assert (
                sum(item.status == OperatingCollectionItemStatus.PENDING.value for item in items)
                == 1
            )
            assert (
                sum(item.failure_code == "COLLECTION_ALREADY_QUEUED" for item in items)
                == 1
            )
    finally:
        _cleanup(postgresql_engine, shops)
        with Session(postgresql_engine) as session:
            session.execute(delete(Team).where(Team.team_id == team_id))
            session.execute(delete(User).where(User.user_id == user_id))
            session.commit()


def test_postgresql_reenable_queues_only_missing_backfill_dates(
    postgresql_engine: Engine,
) -> None:
    """Re-enabling a Shop plans missing days but does not send platform I/O."""

    shops: set[UUID] = set()
    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            shop = _seed_shop(
                session,
                display_name="重新启用补采店铺",
                enabled=False,
            )
            session.flush()
            shops.add(shop.shop_id)
            yesterday = (
                datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=1)
            )
            _service(session).repository.upsert_daily_metric(
                shop_id=shop.shop_id,
                business_date=yesterday,
                source_code="test",
                metric_contract="test-v1",
                turnover_cents=100,
                order_count=1,
                collected_at=datetime.now(UTC),
            )
            session.commit()

            actor = _actor(user_id=uuid4(), team_id=None, super_account=True)
            updated = ShopService(session).update(
                actor,
                shop.shop_id,
                ShopUpdate(enabled=True),
            )
            assert updated.enabled is True

            job = session.scalar(
                select(OperatingDataCollectionJob)
                .join(
                    OperatingDataCollectionItem,
                    OperatingDataCollectionItem.collection_job_id
                    == OperatingDataCollectionJob.collection_job_id,
                )
                .where(
                    OperatingDataCollectionJob.kind == "reenable_backfill",
                    OperatingDataCollectionItem.shop_id == shop.shop_id,
                ),
            )
            assert job is not None
            items = session.scalars(
                select(OperatingDataCollectionItem).where(
                    OperatingDataCollectionItem.collection_job_id == job.collection_job_id,
                ),
            ).all()
            # The default bounded window is 30 days; yesterday was already a
            # persisted success and is deliberately not planned again.
            assert len(items) == 29
            assert all(item.business_date != yesterday for item in items)
            assert all(
                item.status == OperatingCollectionItemStatus.PENDING.value
                for item in items
            )
    finally:
        _cleanup(postgresql_engine, shops)


def test_postgresql_cross_process_claim_keeps_one_running_shop_request(
    postgresql_engine: Engine,
) -> None:
    """A concurrent durable claim loses safely before any platform call."""

    user_id = uuid4()
    team_id = uuid4()
    shops: set[UUID] = set()
    barrier = Barrier(2)
    claims = []
    errors: list[Exception] = []
    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    User(user_id=user_id, display_name="Concurrent claim user"),
                    Team(team_id=team_id, name="Concurrent claim team"),
                ],
            )
            session.flush()
            _grant_dashboard_execution_access(
                session,
                user_id=user_id,
                team_id=team_id,
            )
            shop = _seed_shop(session, display_name="同店串行采集店铺")
            session.flush()
            shops.add(shop.shop_id)
            session.add(TeamShopAccess(team_id=team_id, shop_id=shop.shop_id))
            session.commit()
            _service(session).enqueue_manual_collection(
                actor=_actor(user_id=user_id, team_id=team_id, super_account=False),
                request=OperatingDataCollectionRequest(
                    start_date=DAY_ONE,
                    end_date=DAY_TWO,
                    shop_id=shop.shop_id,
                ),
            )

        now = datetime(2026, 9, 22, tzinfo=UTC)

        def claim_from_independent_session() -> None:
            try:
                with Session(postgresql_engine, expire_on_commit=False) as session:
                    barrier.wait(timeout=5)
                    claims.append(
                        _service(session).prepare_next_collection(
                            now=now,
                            lease_until=now + timedelta(seconds=60),
                        ),
                    )
            except Exception as error:  # pragma: no cover - assertion below
                errors.append(error)

        first = Thread(target=claim_from_independent_session)
        second = Thread(target=claim_from_independent_session)
        first.start()
        second.start()
        first.join(timeout=15)
        second.join(timeout=15)

        assert not first.is_alive()
        assert not second.is_alive()
        assert errors == []
        assert sum(claim is not None for claim in claims) == 1

        with Session(postgresql_engine) as session:
            items = session.scalars(
                select(OperatingDataCollectionItem)
                .where(OperatingDataCollectionItem.shop_id == shop.shop_id)
                .order_by(OperatingDataCollectionItem.business_date),
            ).all()
            assert sum(
                item.status == OperatingCollectionItemStatus.RUNNING.value
                for item in items
            ) == 1
            assert sum(
                item.status == OperatingCollectionItemStatus.PENDING.value
                for item in items
            ) == 1
    finally:
        _cleanup(postgresql_engine, shops)
        with Session(postgresql_engine) as session:
            session.execute(
                delete(TeamModuleAccess).where(TeamModuleAccess.team_id == team_id),
            )
            session.execute(
                delete(TeamMembership).where(TeamMembership.team_id == team_id),
            )
            session.execute(delete(Team).where(Team.team_id == team_id))
            session.execute(delete(User).where(User.user_id == user_id))
            session.commit()


def test_postgresql_global_claim_capacity_applies_across_backend_processes(
    postgresql_engine: Engine,
) -> None:
    """Independent Backend sessions cannot collectively exceed the setting."""

    user_id = uuid4()
    team_id = uuid4()
    shops: set[UUID] = set()
    barrier = Barrier(4)
    claims = []
    errors: list[Exception] = []
    lock = Lock()
    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    User(user_id=user_id, display_name="Global capacity user"),
                    Team(team_id=team_id, name="Global capacity team"),
                ],
            )
            session.flush()
            _grant_dashboard_execution_access(
                session,
                user_id=user_id,
                team_id=team_id,
            )
            seeded = [
                _seed_shop(session, display_name=f"全局容量店铺 {index}")
                for index in range(4)
            ]
            session.flush()
            shops.update(shop.shop_id for shop in seeded)
            session.add_all(
                TeamShopAccess(team_id=team_id, shop_id=shop.shop_id)
                for shop in seeded
            )
            session.commit()
            _service(
                session,
                douyin_compass_collection_concurrency=2,
            ).enqueue_manual_collection(
                actor=_actor(user_id=user_id, team_id=team_id, super_account=False),
                request=OperatingDataCollectionRequest(
                    start_date=DAY_ONE,
                    end_date=DAY_ONE,
                ),
            )

        now = datetime(2026, 9, 22, tzinfo=UTC)

        def claim_from_independent_session() -> None:
            try:
                with Session(postgresql_engine, expire_on_commit=False) as session:
                    barrier.wait(timeout=5)
                    claim = _service(
                        session,
                        douyin_compass_collection_concurrency=2,
                    ).prepare_next_collection(
                        now=now,
                        lease_until=now + timedelta(seconds=60),
                    )
                    with lock:
                        claims.append(claim)
            except Exception as error:  # pragma: no cover - assertion below
                with lock:
                    errors.append(error)

        workers = [Thread(target=claim_from_independent_session) for _ in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=15)

        assert all(not worker.is_alive() for worker in workers)
        assert errors == []
        assert sum(claim is not None for claim in claims) == 2

        with Session(postgresql_engine) as session:
            assert session.scalar(
                select(func.count())
                .select_from(OperatingDataCollectionItem)
                .where(
                    OperatingDataCollectionItem.status
                    == OperatingCollectionItemStatus.RUNNING.value,
                ),
            ) == 2
            assert (
                _service(
                    session,
                    douyin_compass_collection_concurrency=2,
                ).prepare_next_collection(
                    now=now,
                    lease_until=now + timedelta(seconds=60),
                )
                is None
            )
    finally:
        _cleanup(postgresql_engine, shops)
        with Session(postgresql_engine) as session:
            session.execute(
                delete(TeamModuleAccess).where(TeamModuleAccess.team_id == team_id),
            )
            session.execute(
                delete(TeamMembership).where(TeamMembership.team_id == team_id),
            )
            session.execute(delete(Team).where(Team.team_id == team_id))
            session.execute(delete(User).where(User.user_id == user_id))
            session.commit()


def test_postgresql_expired_claim_recovery_rejects_late_executor_result(
    postgresql_engine: Engine,
) -> None:
    """An expired executor cannot overwrite the later claimant's outcome."""

    user_id = uuid4()
    team_id = uuid4()
    shops: set[UUID] = set()
    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    User(user_id=user_id, display_name="Lease recovery user"),
                    Team(team_id=team_id, name="Lease recovery team"),
                ],
            )
            session.flush()
            _grant_dashboard_execution_access(
                session,
                user_id=user_id,
                team_id=team_id,
            )
            shop = _seed_shop(session, display_name="Lease recovery shop")
            session.flush()
            shops.add(shop.shop_id)
            session.add(TeamShopAccess(team_id=team_id, shop_id=shop.shop_id))
            session.commit()
            _service(session).enqueue_manual_collection(
                actor=_actor(user_id=user_id, team_id=team_id, super_account=False),
                request=OperatingDataCollectionRequest(
                    start_date=DAY_ONE,
                    end_date=DAY_ONE,
                    shop_id=shop.shop_id,
                ),
            )

        first_now = datetime(2026, 9, 22, tzinfo=UTC)
        with Session(postgresql_engine, expire_on_commit=False) as session:
            first_claim = _service(session).prepare_next_collection(
                now=first_now,
                lease_until=first_now + timedelta(seconds=10),
            )
        assert first_claim is not None

        recovered_now = first_now + timedelta(seconds=11)
        with Session(postgresql_engine, expire_on_commit=False) as session:
            replacement_claim = _service(session).prepare_next_collection(
                now=recovered_now,
                lease_until=recovered_now + timedelta(seconds=60),
            )
        assert replacement_claim is not None
        assert replacement_claim.collection_item_id == first_claim.collection_item_id
        assert replacement_claim.attempt_count == first_claim.attempt_count + 1

        with Session(postgresql_engine, expire_on_commit=False) as session:
            service = _service(session)
            assert service.finalize_collection(
                claim=first_claim,
                outcome=_success(
                    DailyCollectionRequest(
                        shop_id=shop.shop_id,
                        statistic_date=DAY_ONE,
                    ),
                    turnover=100,
                ),
                now=recovered_now,
            ) is False
            assert session.scalar(
                select(ShopOperatingDailyMetric).where(
                    ShopOperatingDailyMetric.shop_id == shop.shop_id,
                    ShopOperatingDailyMetric.business_date == DAY_ONE,
                ),
            ) is None

        with Session(postgresql_engine, expire_on_commit=False) as session:
            assert _service(session).finalize_collection(
                claim=replacement_claim,
                outcome=_success(
                    DailyCollectionRequest(
                        shop_id=shop.shop_id,
                        statistic_date=DAY_ONE,
                    ),
                    turnover=200,
                ),
                now=recovered_now,
            ) is True
            metric = session.scalar(
                select(ShopOperatingDailyMetric).where(
                    ShopOperatingDailyMetric.shop_id == shop.shop_id,
                    ShopOperatingDailyMetric.business_date == DAY_ONE,
                ),
            )
            assert metric is not None
            assert metric.turnover_cents == 200
    finally:
        _cleanup(postgresql_engine, shops)
        with Session(postgresql_engine) as session:
            session.execute(
                delete(TeamModuleAccess).where(TeamModuleAccess.team_id == team_id),
            )
            session.execute(
                delete(TeamMembership).where(TeamMembership.team_id == team_id),
            )
            session.execute(delete(Team).where(Team.team_id == team_id))
            session.execute(delete(User).where(User.user_id == user_id))
            session.commit()
