from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.modules.access.auth import get_human_principal
from app.modules.access.contracts import ActorContext, HumanPrincipal
from app.modules.access.exceptions import AccessAdministrationForbiddenError
from app.modules.access.module_access import ModuleCode
from app.modules.access.roles import ACCESS_ADMIN_ROLE_CODE
from app.modules.access.service import (
    AccessManagementService,
    ActorContextService,
    ModuleAccessService,
)
from app.modules.human_auth.dependencies import get_password_service
from app.modules.human_auth.passwords import PasswordService


TEAM_CONTEXT_HEADER = "X-Team-ID"


def get_actor_context_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> ActorContextService:
    return ActorContextService(session)


def get_module_access_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> ModuleAccessService:
    return ModuleAccessService(session)


def get_access_management_service(
    session: Annotated[Session, Depends(get_database_session)],
    password_service: Annotated[PasswordService, Depends(get_password_service)],
) -> AccessManagementService:
    return AccessManagementService(session, password_service)


def get_actor_context(
    principal: Annotated[HumanPrincipal, Depends(get_human_principal)],
    service: Annotated[ActorContextService, Depends(get_actor_context_service)],
    requested_team_id: Annotated[
        UUID | None,
        Header(alias=TEAM_CONTEXT_HEADER),
    ] = None,
) -> ActorContext:
    return service.resolve(
        user_id=principal.user_id,
        requested_team_id=requested_team_id,
    )


def get_access_administrator(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
) -> ActorContext:
    if actor.role_code != ACCESS_ADMIN_ROLE_CODE:
        raise AccessAdministrationForbiddenError()
    return actor


def require_module_access(module_code: ModuleCode):
    def get_authorized_actor(
        actor: Annotated[ActorContext, Depends(get_actor_context)],
        service: Annotated[ModuleAccessService, Depends(get_module_access_service)],
    ) -> ActorContext:
        service.require_module_access(actor, module_code)
        return actor

    return get_authorized_actor
