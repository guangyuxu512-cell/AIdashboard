from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.core.security import SecretCipher, get_secret_cipher
from app.modules.notifications.service import NotificationService
from app.modules.workers.auth import (
    get_worker_principal,
    get_worker_provisioning_principal,
)
from app.modules.workers.schemas import (
    DeviceProviderInventoryRead,
    DeviceRuntimeRead,
    DeviceSkillCapabilityRead,
    ProviderInventoryUpsert,
    SkillCapabilitySnapshotUpsert,
    WorkerHeartbeat,
    WorkerProvisioningRead,
)
from app.modules.workers.service import WorkerPrincipal, WorkerService


router = APIRouter(
    prefix="/api/v1/worker",
    tags=["worker"],
    responses={
        **COMMON_ERROR_RESPONSES,
        401: {"model": ErrorResponse, "description": "Worker 身份验证失败"},
    },
)


def get_worker_service(
    session: Annotated[Session, Depends(get_database_session)],
    cipher: Annotated[SecretCipher, Depends(get_secret_cipher)],
) -> WorkerService:
    return WorkerService(
        session,
        notification_service=NotificationService(session, cipher),
    )


@router.get("/provisioning", response_model=WorkerProvisioningRead)
def get_worker_provisioning(
    response: Response,
    principal: Annotated[
        WorkerPrincipal,
        Depends(get_worker_provisioning_principal),
    ],
    service: Annotated[WorkerService, Depends(get_worker_service)],
) -> WorkerProvisioningRead:
    response.headers["Cache-Control"] = "no-store"
    return service.get_provisioning(principal)


@router.post("/heartbeat", response_model=DeviceRuntimeRead)
def heartbeat(
    data: WorkerHeartbeat,
    principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
    service: Annotated[WorkerService, Depends(get_worker_service)],
) -> DeviceRuntimeRead:
    return service.heartbeat(principal, data)


@router.post(
    "/provider-inventory",
    response_model=DeviceProviderInventoryRead,
)
def save_provider_inventory(
    data: ProviderInventoryUpsert,
    principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
    service: Annotated[WorkerService, Depends(get_worker_service)],
) -> DeviceProviderInventoryRead:
    return service.save_provider_inventory(principal, data)


@router.put(
    "/skill-capabilities",
    response_model=list[DeviceSkillCapabilityRead],
)
def sync_skill_capabilities(
    data: SkillCapabilitySnapshotUpsert,
    principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
    service: Annotated[WorkerService, Depends(get_worker_service)],
) -> list[DeviceSkillCapabilityRead]:
    return service.sync_skill_capabilities(principal, data)
