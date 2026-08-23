from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES
from app.modules.automation_apps.schemas import (
    AutomationApplicationConfigRead,
    AutomationApplicationConfigUpsert,
)
from app.modules.automation_apps.service import AutomationApplicationConfigService


router = APIRouter(
    prefix="/api/v1/automation-app-configs",
    tags=["automation-app-configs"],
    responses=COMMON_ERROR_RESPONSES,
)


def get_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> AutomationApplicationConfigService:
    return AutomationApplicationConfigService(session)


@router.get(
    "/{provider_code}/{app_id}",
    response_model=AutomationApplicationConfigRead | None,
)
def get_config(
    provider_code: Literal["yingdao"],
    app_id: str,
    service: Annotated[AutomationApplicationConfigService, Depends(get_service)],
) -> AutomationApplicationConfigRead | None:
    return service.get(provider_code, app_id)


@router.put(
    "/{provider_code}/{app_id}",
    response_model=AutomationApplicationConfigRead,
)
def upsert_config(
    provider_code: Literal["yingdao"],
    app_id: str,
    data: AutomationApplicationConfigUpsert,
    service: Annotated[AutomationApplicationConfigService, Depends(get_service)],
) -> AutomationApplicationConfigRead:
    return service.upsert(provider_code, app_id, data)
