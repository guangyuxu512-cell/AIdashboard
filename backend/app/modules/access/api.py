from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.access.auth import get_human_principal
from app.modules.access.contracts import ActorContext, HumanPrincipal
from app.modules.access.dependencies import (
    get_actor_context,
    get_actor_context_service,
)
from app.modules.access.schemas import ActorContextRead, MyTeamMembershipRead
from app.modules.access.service import ActorContextService


router = APIRouter(
    prefix="/api/v1/access",
    tags=["access"],
    responses={
        **COMMON_ERROR_RESPONSES,
        401: {"model": ErrorResponse, "description": "缺少管理端用户身份"},
        403: {"model": ErrorResponse, "description": "用户或团队成员关系不可用"},
        409: {"model": ErrorResponse, "description": "需要明确团队上下文"},
    },
)


@router.get("/me", response_model=ActorContextRead)
def get_current_actor(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
) -> ActorContextRead:
    return ActorContextRead.model_validate(actor)


@router.get("/me/teams", response_model=list[MyTeamMembershipRead])
def list_my_teams(
    principal: Annotated[HumanPrincipal, Depends(get_human_principal)],
    service: Annotated[ActorContextService, Depends(get_actor_context_service)],
) -> list[MyTeamMembershipRead]:
    return [
        MyTeamMembershipRead.model_validate(item)
        for item in service.list_my_teams(principal.user_id)
    ]
