from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.devices.schemas import DeviceCreate, DeviceRead, DeviceUpdate
from app.modules.devices.service import DeviceService
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


@router.get("", response_model=Page[DeviceRead])
def list_devices(
    pagination: Annotated[PaginationParams, Depends()],
    service: Annotated[DeviceService, Depends(get_device_service)],
) -> Page[DeviceRead]:
    devices, total = service.list(offset=pagination.offset, limit=pagination.page_size)
    return Page[DeviceRead](
        items=[DeviceRead.model_validate(device) for device in devices],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{device_id}", response_model=DeviceRead)
def get_device(
    device_id: UUID,
    service: Annotated[DeviceService, Depends(get_device_service)],
) -> DeviceRead:
    return DeviceRead.model_validate(service.get(device_id))


@router.post("", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
def create_device(
    data: DeviceCreate,
    service: Annotated[DeviceService, Depends(get_device_service)],
) -> DeviceRead:
    return DeviceRead.model_validate(service.create(data))


@router.patch("/{device_id}", response_model=DeviceRead)
def update_device(
    device_id: UUID,
    data: DeviceUpdate,
    service: Annotated[DeviceService, Depends(get_device_service)],
) -> DeviceRead:
    return DeviceRead.model_validate(service.update(device_id, data))
