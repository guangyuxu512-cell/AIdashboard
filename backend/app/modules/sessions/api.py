from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.sessions.schemas import ShopSessionMetadataRead
from app.modules.sessions.service import ShopSessionService


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


@router.get("/{shop_id}/session", response_model=ShopSessionMetadataRead)
def get_shop_session_metadata(
    shop_id: UUID,
    service: Annotated[ShopSessionService, Depends(get_shop_session_service)],
) -> ShopSessionMetadataRead:
    return service.get_metadata(shop_id)
