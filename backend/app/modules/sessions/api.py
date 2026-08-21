from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.core.security import SecretCipher, get_secret_cipher
from app.modules.sessions.auth_context import ShopSessionAccessor
from app.modules.sessions.health_service import ShopSessionHealthService
from app.modules.sessions.refresh_service import ShopSessionRefreshService
from app.modules.sessions.schemas import (
    CompleteShopSessionRefreshCommand,
    ShopSessionHealthRead,
    ShopSessionMetadataRead,
    ShopSessionRefreshLeaseRead,
)
from app.modules.sessions.service import ShopSessionService
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin import DouyinPlatformConnector


router = APIRouter(
    prefix="/api/v1/shops",
    tags=["sessions"],
    responses={
        **COMMON_ERROR_RESPONSES,
        404: {"model": ErrorResponse, "description": "店铺不存在"},
    },
)


def get_shop_session_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> ShopSessionService:
    return ShopSessionService(session)


def get_shop_session_health_service(
    session: Annotated[Session, Depends(get_database_session)],
    cipher: Annotated[SecretCipher, Depends(get_secret_cipher)],
) -> ShopSessionHealthService:
    return ShopSessionHealthService(
        session,
        ShopSessionAccessor(session, cipher),
        {ShopPlatform.DOUYIN: DouyinPlatformConnector()},
        session_service=ShopSessionService(session, cipher),
    )


def get_shop_session_refresh_service(
    session: Annotated[Session, Depends(get_database_session)],
    cipher: Annotated[SecretCipher, Depends(get_secret_cipher)],
) -> ShopSessionRefreshService:
    health_service = ShopSessionHealthService(
        session,
        ShopSessionAccessor(session, cipher),
        {ShopPlatform.DOUYIN: DouyinPlatformConnector()},
        session_service=ShopSessionService(session, cipher),
    )
    return ShopSessionRefreshService(session, cipher, health_service)


@router.get("/{shop_id}/session", response_model=ShopSessionMetadataRead)
def get_shop_session_metadata(
    shop_id: UUID,
    service: Annotated[ShopSessionService, Depends(get_shop_session_service)],
) -> ShopSessionMetadataRead:
    return service.get_metadata(shop_id)


@router.post(
    "/{shop_id}/session/health-check",
    response_model=ShopSessionHealthRead,
    responses={
        401: {"model": ErrorResponse, "description": "平台认证已失效"},
        502: {"model": ErrorResponse, "description": "平台请求或响应失败"},
        504: {"model": ErrorResponse, "description": "平台请求超时"},
    },
)
def validate_shop_session(
    shop_id: UUID,
    service: Annotated[
        ShopSessionHealthService,
        Depends(get_shop_session_health_service),
    ],
) -> ShopSessionHealthRead:
    return service.check(shop_id, force=True)


@router.post(
    "/{shop_id}/session/refresh-lease",
    response_model=ShopSessionRefreshLeaseRead,
    status_code=status.HTTP_201_CREATED,
)
def acquire_shop_session_refresh_lease(
    shop_id: UUID,
    service: Annotated[
        ShopSessionRefreshService,
        Depends(get_shop_session_refresh_service),
    ],
) -> ShopSessionRefreshLeaseRead:
    return service.acquire(shop_id)


@router.delete(
    "/{shop_id}/session/refresh-lease/{lease_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def release_shop_session_refresh_lease(
    shop_id: UUID,
    lease_id: UUID,
    service: Annotated[
        ShopSessionRefreshService,
        Depends(get_shop_session_refresh_service),
    ],
) -> Response:
    service.release(shop_id, lease_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{shop_id}/session/refresh",
    response_model=ShopSessionHealthRead,
    responses={
        401: {"model": ErrorResponse, "description": "新会话认证无效"},
        409: {"model": ErrorResponse, "description": "恢复租约或版本冲突"},
        502: {"model": ErrorResponse, "description": "平台请求或响应失败"},
        504: {"model": ErrorResponse, "description": "平台请求超时"},
    },
)
def complete_shop_session_refresh(
    shop_id: UUID,
    command: CompleteShopSessionRefreshCommand,
    service: Annotated[
        ShopSessionRefreshService,
        Depends(get_shop_session_refresh_service),
    ],
) -> ShopSessionHealthRead:
    return service.complete(shop_id, command)
