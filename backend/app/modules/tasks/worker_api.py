from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.core.security import SecretCipher, get_secret_cipher
from app.modules.assets.api import get_asset_service
from app.modules.assets.service import AssetService
from app.modules.credentials.service import CredentialService
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
    cipher: Annotated[SecretCipher, Depends(get_secret_cipher)],
) -> TaskService:
    return TaskService(
        session,
        credential_service=CredentialService(session, cipher),
    )


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
    claimed = service.claim_with_account(principal)
    if claimed is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    task = claimed.task
    return WorkerTaskRead(
        task_id=task.task_id,
        skill_id=task.skill_id,
        input=task.input_json,
        lease_until=task.lease_until,
        accounts=claimed.accounts,
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


@router.get("/{task_id}/assets/{asset_id}", response_class=FileResponse)
def download_task_asset(
    task_id: UUID,
    asset_id: UUID,
    principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
    service: Annotated[AssetService, Depends(get_asset_service)],
) -> FileResponse:
    asset, path = service.get_worker_content(
        principal,
        task_id=task_id,
        asset_id=asset_id,
    )
    return FileResponse(
        path,
        media_type=asset.content_type,
        headers={"Content-Disposition": "inline"},
    )


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
