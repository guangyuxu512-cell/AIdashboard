import asyncio
from datetime import UTC, date, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient, Response

from app.main import create_app
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.operating_dashboard.api import (
    get_operating_dashboard_actor,
    get_operating_dashboard_service,
)
from app.modules.operating_dashboard.schemas import (
    OperatingDashboardComparisonRead,
    OperatingDashboardCoverageRead,
    OperatingDashboardDateRangeRead,
    OperatingDashboardRead,
    OperatingDashboardShopOptionRead,
    OperatingDashboardSummaryRead,
    OperatingDashboardTablePageRead,
    OperatingDashboardTableRowRead,
    OperatingDashboardTrendPointRead,
    OperatingDataCollectionCountsRead,
    OperatingDataCollectionJobRead,
)
from app.modules.shops.enums import ShopPlatform


ACTOR = ActorContext(
    user_id=uuid4(),
    user_display_name="经营看板接口测试用户",
    team_id=uuid4(),
    membership_id=uuid4(),
    role_code="member",
    data_scope=DataScope.TEAM,
)
SHOP_ID = uuid4()
JOB_ID = uuid4()


def dashboard_read() -> OperatingDashboardRead:
    selected_range = OperatingDashboardDateRangeRead(
        start_date=date(2026, 9, 20),
        end_date=date(2026, 9, 20),
    )
    unavailable = OperatingDashboardComparisonRead(state="unavailable")
    return OperatingDashboardRead(
        date_range=selected_range,
        comparison_date_range=OperatingDashboardDateRangeRead(
            start_date=date(2026, 9, 19),
            end_date=date(2026, 9, 19),
        ),
        trend_date_range=OperatingDashboardDateRangeRead(
            start_date=date(2026, 9, 14),
            end_date=date(2026, 9, 20),
        ),
        all_available_shops=[
            OperatingDashboardShopOptionRead(
                shop_id=SHOP_ID,
                shop_name="接口测试店铺",
                platform=ShopPlatform.DOUYIN,
            ),
        ],
        summary=OperatingDashboardSummaryRead(
            turnover_cents=100,
            order_count=2,
            return_quantity=None,
            shop_count=1,
            turnover_comparison=unavailable,
            order_comparison=unavailable,
            return_comparison=unavailable,
            shop_count_comparison=unavailable,
        ),
        trend=[
            OperatingDashboardTrendPointRead(
                business_date=date(2026, 9, 20),
                turnover_cents=100,
                order_count=2,
            ),
        ],
        table=OperatingDashboardTablePageRead(
            items=[
                OperatingDashboardTableRowRead(
                    shop_id=SHOP_ID,
                    shop_name="接口测试店铺",
                    platform=ShopPlatform.DOUYIN,
                    turnover_cents=100,
                    order_count=2,
                    return_quantity=None,
                    collected_at=datetime(2026, 9, 21, tzinfo=UTC),
                    coverage_complete=True,
                ),
            ],
            total=1,
            page=2,
            page_size=10,
        ),
        coverage=OperatingDashboardCoverageRead(
            state="available",
            supported_shop_count=1,
            collected_shop_days=1,
            total_shop_days=1,
            missing_shop_days=0,
            missing_samples=[],
            missing_samples_truncated=False,
            manual_backfill_required=False,
        ),
        collection_available=True,
    )


def collection_job() -> OperatingDataCollectionJobRead:
    now = datetime(2026, 9, 21, tzinfo=UTC)
    return OperatingDataCollectionJobRead(
        collection_job_id=JOB_ID,
        kind="manual_refresh",
        status="pending",
        requested_start_date=date(2026, 9, 20),
        requested_end_date=date(2026, 9, 20),
        created_at=now,
        updated_at=now,
        started_at=None,
        finished_at=None,
        counts=OperatingDataCollectionCountsRead(
            pending=1,
            running=0,
            succeeded=0,
            failed=0,
            skipped=0,
            paused_reauthorization=0,
        ),
        items=[],
    )


class DashboardServiceStub:
    def __init__(self) -> None:
        self.read_calls: list[dict[str, object]] = []
        self.enqueue_calls: list[dict[str, object]] = []

    def read(self, **kwargs: object) -> OperatingDashboardRead:
        self.read_calls.append(kwargs)
        return dashboard_read()

    def enqueue_manual_collection(self, **kwargs: object) -> OperatingDataCollectionJobRead:
        self.enqueue_calls.append(kwargs)
        return collection_job()

    def get_collection_job(self, **_: object) -> OperatingDataCollectionJobRead:
        return collection_job()

    def retry_failed_collection_items(self, **_: object) -> OperatingDataCollectionJobRead:
        return collection_job()


def request(
    method: str,
    path: str,
    *,
    service: DashboardServiceStub,
    **kwargs: object,
) -> Response:
    application = create_app()
    application.dependency_overrides[get_operating_dashboard_actor] = lambda: ACTOR
    application.dependency_overrides[get_operating_dashboard_service] = lambda: service

    async def send() -> Response:
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_read_uses_formal_sort_and_pagination_contract() -> None:
    service = DashboardServiceStub()

    response = request(
        "GET",
        "/api/v1/operating-dashboard?start_date=2026-09-20&end_date=2026-09-20&page=2&page_size=10&sort_field=turnover_cents&sort_direction=desc",
        service=service,
    )

    assert response.status_code == 200
    assert response.json()["table"]["page"] == 2
    assert response.json()["table"]["items"][0]["return_quantity"] is None
    assert service.read_calls[0]["sort_field"] == "turnover_cents"
    assert service.read_calls[0]["sort_direction"] == "desc"
    pagination = service.read_calls[0]["pagination"]
    assert getattr(pagination, "page") == 2
    assert getattr(pagination, "page_size") == 10


def test_read_rejects_half_of_a_sort_contract_before_service_execution() -> None:
    service = DashboardServiceStub()

    response = request(
        "GET",
        "/api/v1/operating-dashboard?start_date=2026-09-20&end_date=2026-09-20&sort_field=turnover_cents",
        service=service,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "OPERATING_DASHBOARD_INVALID_REQUEST"
    assert service.read_calls == []


def test_manual_update_returns_a_durable_job_instead_of_waiting_for_platform_io() -> None:
    service = DashboardServiceStub()

    response = request(
        "POST",
        "/api/v1/operating-dashboard/collections",
        service=service,
        json={
            "start_date": "2026-09-20",
            "end_date": "2026-09-20",
            "shop_id": str(SHOP_ID),
        },
    )

    assert response.status_code == 202
    assert response.json()["collection_job_id"] == str(JOB_ID)
    assert service.enqueue_calls[0]["actor"] == ACTOR
