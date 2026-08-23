from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.devices.schemas import DeviceCreate, DeviceRead, DeviceUpdate
from app.modules.devices.service import DeviceService
from app.modules.devices.models import Device
from app.modules.workers.schemas import (
    DeviceProviderInventoryRead,
    DeviceRuntimeRead,
    DeviceSkillCapabilityRead,
    WorkerCredentialRead,
    WorkerTokenIssuedRead,
)
from app.modules.workers.service import WorkerService
from app.shared.pagination import Page, PaginationParams


router = APIRouter(
    prefix="/api/v1/devices",
    tags=["devices"],
    responses={
        **COMMON_ERROR_RESPONSES,
        404: {"model": ErrorResponse, "description": "设备不存在"},
    },
)


def get_device_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> DeviceService:
    return DeviceService(session)


def get_worker_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> WorkerService:
    return WorkerService(session)


def to_device_read(
    device: Device,
    runtime: DeviceRuntimeRead | None,
) -> DeviceRead:
    return DeviceRead.model_validate(device).model_copy(
        update={"worker_runtime": runtime},
    )


@router.get("", response_model=Page[DeviceRead])
def list_devices(
    pagination: Annotated[PaginationParams, Depends()],
    service: Annotated[DeviceService, Depends(get_device_service)],
    worker_service: Annotated[WorkerService, Depends(get_worker_service)],
) -> Page[DeviceRead]:
    devices, total = service.list(offset=pagination.offset, limit=pagination.page_size)
    runtimes = worker_service.get_runtime_reads(
        [device.device_id for device in devices],
    )
    return Page[DeviceRead](
        items=[
            to_device_read(device, runtimes.get(device.device_id))
            for device in devices
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{device_id}", response_model=DeviceRead)
def get_device(
    device_id: UUID,
    service: Annotated[DeviceService, Depends(get_device_service)],
    worker_service: Annotated[WorkerService, Depends(get_worker_service)],
) -> DeviceRead:
    device = service.get(device_id)
    runtime = worker_service.get_runtime_reads([device_id]).get(device_id)
    return to_device_read(device, runtime)


@router.get(
    "/{device_id}/provider-inventories",
    response_model=list[DeviceProviderInventoryRead],
)
def get_device_provider_inventories(
    device_id: UUID,
    service: Annotated[DeviceService, Depends(get_device_service)],
    worker_service: Annotated[WorkerService, Depends(get_worker_service)],
) -> list[DeviceProviderInventoryRead]:
    service.get(device_id)
    return worker_service.get_provider_inventory_reads(device_id)


@router.get(
    "/{device_id}/skill-capabilities",
    response_model=list[DeviceSkillCapabilityRead],
)
def get_device_skill_capabilities(
    device_id: UUID,
    service: Annotated[DeviceService, Depends(get_device_service)],
    worker_service: Annotated[WorkerService, Depends(get_worker_service)],
) -> list[DeviceSkillCapabilityRead]:
    service.get(device_id)
    return worker_service.get_skill_capability_reads(device_id)


@router.get(
    "/{device_id}/worker-credential",
    response_model=WorkerCredentialRead,
)
def get_worker_credential(
    device_id: UUID,
    service: Annotated[WorkerService, Depends(get_worker_service)],
) -> WorkerCredentialRead:
    return service.get_credential(device_id)


@router.post(
    "/{device_id}/worker-credential/issue",
    response_model=WorkerTokenIssuedRead,
)
def issue_worker_credential(
    device_id: UUID,
    response: Response,
    service: Annotated[WorkerService, Depends(get_worker_service)],
) -> WorkerTokenIssuedRead:
    response.headers["Cache-Control"] = "no-store"
    return service.issue_credential(device_id)


@router.post(
    "/{device_id}/worker-credential/rotate",
    response_model=WorkerTokenIssuedRead,
)
def rotate_worker_credential(
    device_id: UUID,
    response: Response,
    service: Annotated[WorkerService, Depends(get_worker_service)],
) -> WorkerTokenIssuedRead:
    response.headers["Cache-Control"] = "no-store"
    return service.rotate_credential(device_id)


@router.post(
    "/{device_id}/worker-credential/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_worker_credential(
    device_id: UUID,
    service: Annotated[WorkerService, Depends(get_worker_service)],
) -> None:
    service.disable_token(device_id)


@router.post("", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
def create_device(
    data: DeviceCreate,
    service: Annotated[DeviceService, Depends(get_device_service)],
) -> DeviceRead:
    return to_device_read(service.create(data), None)


@router.patch("/{device_id}", response_model=DeviceRead)
def update_device(
    device_id: UUID,
    data: DeviceUpdate,
    service: Annotated[DeviceService, Depends(get_device_service)],
) -> DeviceRead:
    return to_device_read(service.update(device_id, data), None)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_device(
    device_id: UUID,
    service: Annotated[DeviceService, Depends(get_device_service)],
) -> None:
    service.remove(device_id)
