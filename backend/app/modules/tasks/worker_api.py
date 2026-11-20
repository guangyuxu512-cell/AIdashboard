from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.assets.api import asset_content_response, get_asset_service
from app.modules.assets.service import AssetService
from app.modules.tasks.schemas import (
    TaskComplete,
    TaskEventBatchResult,
    TaskEventBatchWrite,
    TaskFail,
    TaskLeaseRead,
    TaskRead,
    WorkerTaskAssetRead,
    WorkerTaskRead,
    task_to_read,
)
from app.modules.tasks.service import TaskService
from app.modules.workers.auth import get_worker_principal
from app.modules.workers.precheck_service import session_snapshot_expired
from app.modules.workers.service import WorkerPrincipal


router = APIRouter(
    prefix="/api/v1/worker/tasks",
    tags=["worker"],
    responses={
        **COMMON_ERROR_RESPONSES,
        401: {"model": ErrorResponse, "description": "Worker 身份验证失败"},
        409: {"model": ErrorResponse, "description": "任务 Lease 或状态已失效"},
    },
)


def get_worker_task_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> TaskService:
    return TaskService(session)


@router.post(
    "/claim",
    response_model=WorkerTaskRead,
    response_model_exclude_defaults=True,
    responses={204: {"description": "当前设备没有待执行任务"}},
)
def claim_task(
    principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
    service: Annotated[TaskService, Depends(get_worker_task_service)],
) -> WorkerTaskRead | Response:
    return _claim_worker_task(principal, service)


@router.post(
    "/claim-precheck",
    response_model=WorkerTaskRead,
    response_model_exclude_defaults=True,
    responses={204: {"description": "当前设备没有可并行的预检任务"}},
)
def claim_precheck_task(
    principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
    service: Annotated[TaskService, Depends(get_worker_task_service)],
) -> WorkerTaskRead | Response:
    return _claim_worker_task(principal, service, precheck_only=True)


def _claim_worker_task(
    principal: WorkerPrincipal,
    service: TaskService,
    *,
    precheck_only: bool = False,
) -> WorkerTaskRead | Response:
    claimed = (service.claim_with_context(principal, precheck_only=True)
               if precheck_only else service.claim_with_context(principal))
    if claimed is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    task = claimed.task
    direct_product = task.skill_id == "douyin.category_schema" and task.input_json.get("_result_delivery") == "product"
    from app.modules.workers.shop_context import LOCAL_SHOPS_KEY
    task_input = ({key: value for key, value in task.input_json.items() if not key.startswith("_")}
                  if task.skill_id in {"douyin.category_schema", "douyin.compass_selection"} else
                  {key: value for key, value in task.input_json.items() if key != LOCAL_SHOPS_KEY})
    if task.skill_id == "douyin.category_schema" and session_snapshot_expired(service.session, task):
        task_input["skip_expired_session"] = True
    return WorkerTaskRead(
        task_id=task.task_id,
        skill_id=task.skill_id,
        input=task_input,
        result_delivery=("product" if direct_product else
                         "operations" if task.skill_id == "douyin.compass_selection" else "central"),
        lease_until=task.lease_until,
        local_shops=claimed.local_shops,
        assets=[
            WorkerTaskAssetRead(
                asset_id=asset.asset_id,
                filename=asset.original_filename,
                position=position,
                content_type=asset.content_type,
                size_bytes=asset.size_bytes,
                sha256=asset.sha256,
                download_path=(
                    f"/api/v1/worker/tasks/{task.task_id}/assets/{asset.asset_id}"
                ),
            )
            for position, asset in enumerate(claimed.assets)
        ],
    )


@router.get("/{task_id}/assets/{asset_id}", response_class=StreamingResponse)
def download_task_asset(
    task_id: UUID,
    asset_id: UUID,
    principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
    service: Annotated[AssetService, Depends(get_asset_service)],
) -> StreamingResponse:
    asset, content = service.get_worker_content(
        principal,
        task_id=task_id,
        asset_id=asset_id,
    )
    return asset_content_response(asset.content_type, asset.size_bytes, content)


@router.post("/{task_id}/renew", response_model=TaskLeaseRead)
def renew_task(
    task_id: UUID,
    principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
    service: Annotated[TaskService, Depends(get_worker_task_service)],
) -> TaskLeaseRead:
    task = service.renew(principal, task_id)
    return TaskLeaseRead(
        task_id=task.task_id,
        status=task.status,
        lease_until=task.lease_until,
    )


@router.post("/{task_id}/complete", response_model=TaskRead)
def complete_task(
    task_id: UUID,
    data: TaskComplete,
    principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
    service: Annotated[TaskService, Depends(get_worker_task_service)],
) -> TaskRead:
    return task_to_read(service.complete(principal, task_id, data))


@router.post("/{task_id}/fail", response_model=TaskRead)
def fail_task(
    task_id: UUID,
    data: TaskFail,
    principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
    service: Annotated[TaskService, Depends(get_worker_task_service)],
) -> TaskRead:
    return task_to_read(service.fail(principal, task_id, data))


@router.post("/{task_id}/events", response_model=TaskEventBatchResult)
def append_task_events(
    task_id: UUID,
    data: TaskEventBatchWrite,
    principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
    service: Annotated[TaskService, Depends(get_worker_task_service)],
) -> TaskEventBatchResult:
    return service.append_events(principal, task_id, data)
