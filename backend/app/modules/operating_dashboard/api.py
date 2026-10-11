from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import require_module_access
from app.modules.access.module_access import ModuleCode
from app.modules.operating_dashboard.schemas import (
    OperatingDashboardRead,
    OperatingDataCollectionJobRead,
    OperatingDataCollectionRequest,
    OperatingDataCollectionRetryRequest,
    OperatingDataCollectionSubmissionRead,
)
from app.modules.operating_dashboard.exceptions import (
    OperatingDashboardInvalidRequestError,
)
from app.modules.operating_dashboard.service import (
    DashboardSortDirection,
    DashboardSortField,
    OperatingDashboardService,
)
from app.modules.shops.enums import ShopPlatform
from app.shared.pagination import PaginationParams


router = APIRouter(
    prefix="/api/v1/operating-dashboard",
    tags=["operating-dashboard"],
    responses={
        **COMMON_ERROR_RESPONSES,
        404: {"model": ErrorResponse, "description": "店铺或采集任务不存在"},
        409: {"model": ErrorResponse, "description": "采集任务当前不可重试"},
        503: {"model": ErrorResponse, "description": "当前环境未启用经营数据采集"},
    },
)

get_operating_dashboard_actor = require_module_access(ModuleCode.SHOP)


def get_operating_dashboard_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> OperatingDashboardService:
    return OperatingDashboardService(session)


@router.get("", response_model=OperatingDashboardRead)
def read_operating_dashboard(
    actor: Annotated[ActorContext, Depends(get_operating_dashboard_actor)],
    service: Annotated[
        OperatingDashboardService,
        Depends(get_operating_dashboard_service),
    ],
    pagination: Annotated[PaginationParams, Depends()],
    start_date: Annotated[date, Query()],
    end_date: Annotated[date, Query()],
    platform: Annotated[ShopPlatform | None, Query()] = None,
    shop_id: Annotated[UUID | None, Query()] = None,
    sort_field: Annotated[DashboardSortField | None, Query()] = None,
    sort_direction: Annotated[DashboardSortDirection | None, Query()] = None,
) -> OperatingDashboardRead:
    if (sort_field is None) != (sort_direction is None):
        raise OperatingDashboardInvalidRequestError("排序字段与方向必须同时提供")
    return service.read(
        actor=actor,
        start_date=start_date,
        end_date=end_date,
        platform=platform,
        shop_id=shop_id,
        sort_field=sort_field,
        sort_direction=sort_direction,
        pagination=pagination,
    )


@router.post(
    "/collections",
    response_model=OperatingDataCollectionSubmissionRead,
)
def enqueue_operating_collection(
    request: OperatingDataCollectionRequest,
    actor: Annotated[ActorContext, Depends(get_operating_dashboard_actor)],
    service: Annotated[
        OperatingDashboardService,
        Depends(get_operating_dashboard_service),
    ],
) -> OperatingDataCollectionSubmissionRead:
    return service.request_collection_update(
        actor=actor,
        request=request,
        force_recollect=False,
    )


@router.post(
    "/collections/recollect",
    response_model=OperatingDataCollectionSubmissionRead,
)
def recollect_operating_collection(
    request: OperatingDataCollectionRequest,
    actor: Annotated[ActorContext, Depends(get_operating_dashboard_actor)],
    service: Annotated[
        OperatingDashboardService,
        Depends(get_operating_dashboard_service),
    ],
) -> OperatingDataCollectionSubmissionRead:
    """Explicitly refresh the selected persisted scope after user intent."""

    return service.request_collection_update(
        actor=actor,
        request=request,
        force_recollect=True,
    )


@router.get(
    "/collections/{collection_job_id}",
    response_model=OperatingDataCollectionJobRead,
)
def get_operating_collection(
    collection_job_id: UUID,
    actor: Annotated[ActorContext, Depends(get_operating_dashboard_actor)],
    service: Annotated[
        OperatingDashboardService,
        Depends(get_operating_dashboard_service),
    ],
) -> OperatingDataCollectionJobRead:
    return service.get_collection_job(
        actor=actor,
        collection_job_id=collection_job_id,
    )


@router.post(
    "/collections/{collection_job_id}/retry",
    response_model=OperatingDataCollectionJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_operating_collection(
    collection_job_id: UUID,
    request: OperatingDataCollectionRetryRequest,
    actor: Annotated[ActorContext, Depends(get_operating_dashboard_actor)],
    service: Annotated[
        OperatingDashboardService,
        Depends(get_operating_dashboard_service),
    ],
) -> OperatingDataCollectionJobRead:
    return service.retry_failed_collection_items(
        actor=actor,
        collection_job_id=collection_job_id,
        item_ids=request.item_ids,
        session_recovery_version=request.session_recovery_version,
    )
