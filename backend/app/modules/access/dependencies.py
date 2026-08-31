from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.modules.access.auth import get_human_principal
from app.modules.access.contracts import ActorContext, HumanPrincipal
from app.modules.access.service import ActorContextService


TEAM_CONTEXT_HEADER = "X-Team-ID"


def get_actor_context_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> ActorContextService:
    return ActorContextService(session)


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
