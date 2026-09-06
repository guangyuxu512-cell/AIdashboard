from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.core.security import SecretCipher, get_secret_cipher
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import require_module_access
from app.modules.access.module_access import ModuleCode
from app.modules.notifications.schemas import (
    NotificationChannelCreate,
    NotificationChannelRead,
    NotificationChannelUpdate,
    NotificationTestRead,
)
from app.modules.notifications.service import NotificationService


router = APIRouter(
    prefix="/api/v1/notification-channels",
    tags=["notification-channels"],
    responses={
        **COMMON_ERROR_RESPONSES,
        404: {"model": ErrorResponse, "description": "通知通道不存在"},
        502: {"model": ErrorResponse, "description": "通知发送失败"},
    },
)


get_settings_authorized_actor = require_module_access(ModuleCode.SETTINGS)


def get_notification_service(
    session: Annotated[Session, Depends(get_database_session)],
    cipher: Annotated[SecretCipher, Depends(get_secret_cipher)],
) -> NotificationService:
    return NotificationService(session, cipher)


@router.get("", response_model=list[NotificationChannelRead])
def list_notification_channels(
    _actor: Annotated[ActorContext, Depends(get_settings_authorized_actor)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> list[NotificationChannelRead]:
    return service.list_channels()


@router.post(
    "",
    response_model=NotificationChannelRead,
    status_code=status.HTTP_201_CREATED,
)
def create_notification_channel(
    data: NotificationChannelCreate,
    _actor: Annotated[ActorContext, Depends(get_settings_authorized_actor)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationChannelRead:
    return service.create_channel(data)


@router.patch("/{channel_id}", response_model=NotificationChannelRead)
def update_notification_channel(
    channel_id: UUID,
    data: NotificationChannelUpdate,
    _actor: Annotated[ActorContext, Depends(get_settings_authorized_actor)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationChannelRead:
    return service.update_channel(channel_id, data)


@router.post("/{channel_id}/test", response_model=NotificationTestRead)
def test_notification_channel(
    channel_id: UUID,
    _actor: Annotated[ActorContext, Depends(get_settings_authorized_actor)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationTestRead:
    service.send_test(channel_id, now=datetime.now(UTC))
    return NotificationTestRead(delivered=True)
