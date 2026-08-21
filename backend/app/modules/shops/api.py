from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.core.security import SecretCipher, get_secret_cipher
from app.modules.sessions.auth_context import ShopSessionAccessor
from app.modules.sessions.health_service import ShopSessionHealthService
from app.modules.sessions.service import ShopSessionService
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.platform_service import ShopPlatformService
from app.modules.shops.schemas import (
    ShopCreate,
    ShopDeviceBindingCreate,
    ShopDeviceBindingRead,
    ShopDeviceBindingUpdate,
    ShopListRead,
    ShopRead,
    ShopUpdate,
)
from app.modules.shops.service import ShopService
from app.platforms.douyin import DouyinPlatformConnector
from app.platforms.schemas import PlatformShopIdentityRead
from app.shared.pagination import Page, PaginationParams


router = APIRouter(
    prefix="/api/v1/shops",
    tags=["shops"],
    responses={
        **COMMON_ERROR_RESPONSES,
        404: {"model": ErrorResponse, "description": "店铺或关联实体不存在"},
        409: {"model": ErrorResponse, "description": "设备绑定关系无效"},
    },
)


def get_shop_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> ShopService:
    return ShopService(session)


def get_shop_platform_service(
    session: Annotated[Session, Depends(get_database_session)],
    cipher: Annotated[SecretCipher, Depends(get_secret_cipher)],
) -> ShopPlatformService:
    health_service = ShopSessionHealthService(
        session,
        ShopSessionAccessor(session, cipher),
        {ShopPlatform.DOUYIN: DouyinPlatformConnector()},
        session_service=ShopSessionService(session, cipher),
    )
    return ShopPlatformService(health_service)


@router.get("", response_model=Page[ShopListRead])
def list_shops(
    pagination: Annotated[PaginationParams, Depends()],
    service: Annotated[ShopService, Depends(get_shop_service)],
) -> Page[ShopListRead]:
    shops, total, session_statuses = service.list(
        offset=pagination.offset,
        limit=pagination.page_size,
    )
    return Page[ShopListRead](
        items=[
            ShopListRead(
                **ShopRead.model_validate(shop).model_dump(),
                session_status=session_statuses.get(shop.shop_id),
            )
            for shop in shops
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{shop_id}", response_model=ShopRead)
def get_shop(
    shop_id: UUID,
    service: Annotated[ShopService, Depends(get_shop_service)],
) -> ShopRead:
    return ShopRead.model_validate(service.get(shop_id))


@router.get(
    "/{shop_id}/platform-identity",
    response_model=PlatformShopIdentityRead,
    responses={
        401: {"model": ErrorResponse, "description": "平台认证已失效"},
        502: {"model": ErrorResponse, "description": "平台请求或响应失败"},
        504: {"model": ErrorResponse, "description": "平台请求超时"},
    },
)
def get_platform_shop_identity(
    shop_id: UUID,
    service: Annotated[
        ShopPlatformService,
        Depends(get_shop_platform_service),
    ],
) -> PlatformShopIdentityRead:
    return service.fetch_identity(shop_id)


@router.post("", response_model=ShopRead, status_code=status.HTTP_201_CREATED)
def create_shop(
    data: ShopCreate,
    service: Annotated[ShopService, Depends(get_shop_service)],
) -> ShopRead:
    return ShopRead.model_validate(service.create(data))


@router.patch("/{shop_id}", response_model=ShopRead)
def update_shop(
    shop_id: UUID,
    data: ShopUpdate,
    service: Annotated[ShopService, Depends(get_shop_service)],
) -> ShopRead:
    return ShopRead.model_validate(service.update(shop_id, data))


@router.delete("/{shop_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_shop(
    shop_id: UUID,
    service: Annotated[ShopService, Depends(get_shop_service)],
) -> None:
    service.remove(shop_id)


@router.get("/{shop_id}/device-bindings", response_model=list[ShopDeviceBindingRead])
def list_shop_device_bindings(
    shop_id: UUID,
    service: Annotated[ShopService, Depends(get_shop_service)],
) -> list[ShopDeviceBindingRead]:
    return [
        ShopDeviceBindingRead.model_validate(binding)
        for binding in service.list_bindings(shop_id)
    ]


@router.post(
    "/{shop_id}/device-bindings",
    response_model=ShopDeviceBindingRead,
    status_code=status.HTTP_201_CREATED,
)
def create_shop_device_binding(
    shop_id: UUID,
    data: ShopDeviceBindingCreate,
    service: Annotated[ShopService, Depends(get_shop_service)],
) -> ShopDeviceBindingRead:
    return ShopDeviceBindingRead.model_validate(service.create_binding(shop_id, data))


@router.patch(
    "/{shop_id}/device-bindings/{device_id}",
    response_model=ShopDeviceBindingRead,
)
def update_shop_device_binding(
    shop_id: UUID,
    device_id: UUID,
    data: ShopDeviceBindingUpdate,
    service: Annotated[ShopService, Depends(get_shop_service)],
) -> ShopDeviceBindingRead:
    return ShopDeviceBindingRead.model_validate(
        service.update_binding(shop_id, device_id, data),
    )
