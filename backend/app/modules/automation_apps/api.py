from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import require_module_access
from app.modules.access.module_access import ModuleCode
from app.modules.automation_apps.schemas import (
    AutomationApplicationConfigRead,
    AutomationApplicationConfigUpsert,
    YingdaoApplicationOptionRead,
)
from app.modules.automation_apps.service import (
    AutomationApplicationCatalogService,
    AutomationApplicationConfigService,
)


router = APIRouter(
    prefix="/api/v1/automation-app-configs",
    tags=["automation-app-configs"],
    responses=COMMON_ERROR_RESPONSES,
)


get_device_authorized_actor = require_module_access(ModuleCode.DEVICE)


def get_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> AutomationApplicationConfigService:
    return AutomationApplicationConfigService(session)


def get_catalog_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> AutomationApplicationCatalogService:
    return AutomationApplicationCatalogService(session)


@router.get(
    "/yingdao/applications",
    response_model=list[YingdaoApplicationOptionRead],
)
def list_yingdao_applications(
    actor: Annotated[ActorContext, Depends(get_device_authorized_actor)],
    service: Annotated[
        AutomationApplicationCatalogService,
        Depends(get_catalog_service),
    ],
) -> list[YingdaoApplicationOptionRead]:
    return service.list_yingdao_application_options(actor=actor)


@router.get(
    "/{provider_code}/{app_id}",
    response_model=AutomationApplicationConfigRead | None,
)
def get_config(
    provider_code: Literal["yingdao"],
    app_id: str,
    _actor: Annotated[ActorContext, Depends(get_device_authorized_actor)],
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
    _actor: Annotated[ActorContext, Depends(get_device_authorized_actor)],
    service: Annotated[AutomationApplicationConfigService, Depends(get_service)],
) -> AutomationApplicationConfigRead:
    return service.upsert(provider_code, app_id, data)
