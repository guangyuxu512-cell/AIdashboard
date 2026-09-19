from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status

from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.core.logging.request import get_request_id
from app.modules.access.auth import get_human_principal
from app.modules.access.contracts import ActorContext, HumanPrincipal, ManagedMember
from app.modules.access.dependencies import (
    TEAM_CONTEXT_HEADER,
    get_access_management_service,
    get_actor_context,
    get_actor_context_service,
    get_module_access_service,
    get_super_account,
)
from app.modules.access.exceptions import TeamMembershipRequiredError
from app.modules.access.schemas import (
    AccessMemberCreate,
    AccessMemberPasswordReset,
    AccessMemberRead,
    AccessMemberTeamUpdate,
    AccessMemberUpdate,
    AccessMembershipCreate,
    AccessMembershipRead,
    AccessMembershipUpdate,
    CurrentModuleAccessRead,
    TeamAuthorizationRead,
    TeamAuthorizationUpdate,
    TeamCreate,
    TeamRead,
    TeamUpdate,
)
from app.modules.access.service import (
    AccessManagementService,
    ActorContextService,
    ModuleAccessService,
)
from app.shared.pagination import Page, PaginationParams


ACCESS_MANAGEMENT_ERROR_RESPONSES = cast(
    dict[int | str, dict[str, Any]],
    COMMON_ERROR_RESPONSES.copy(),
)
ACCESS_MANAGEMENT_ERROR_RESPONSES.update(
    {
        401: {"model": ErrorResponse, "description": "需要有效的管理端用户身份"},
        403: {"model": ErrorResponse, "description": "当前用户无权管理用户与权限"},
        404: {"model": ErrorResponse, "description": "人员、团队或成员关系不存在"},
        409: {"model": ErrorResponse, "description": "当前状态不允许该管理操作"},
        422: {"model": ErrorResponse, "description": "请求字段或模块权限配置无效"},
    },
)


router = APIRouter(
    prefix="/api/v1/access-management",
    tags=["access-management"],
    responses=ACCESS_MANAGEMENT_ERROR_RESPONSES,
)


def _member_read(member: ManagedMember) -> AccessMemberRead:
    return AccessMemberRead(
        user_id=member.user_id,
        display_name=member.display_name,
        login_name=member.login_name,
        enabled=member.enabled,
        is_super_account=member.is_super_account,
        memberships=[
            AccessMembershipRead(
                membership_id=membership.membership_id,
                team_id=membership.team_id,
                team_name=membership.team_name,
                team_enabled=membership.team_enabled,
                role_code=membership.role_code,
                data_scope=membership.data_scope,
                enabled=membership.enabled,
                module_codes=list(membership.module_codes),
            )
            for membership in member.memberships
        ],
        created_at=member.created_at,
        updated_at=member.updated_at,
    )


@router.get("/me/module-access", response_model=CurrentModuleAccessRead)
def get_current_module_access(
    principal: Annotated[HumanPrincipal, Depends(get_human_principal)],
    actor_context_service: Annotated[
        ActorContextService,
        Depends(get_actor_context_service),
    ],
    service: Annotated[ModuleAccessService, Depends(get_module_access_service)],
    requested_team_id: Annotated[
        UUID | None,
        Header(alias=TEAM_CONTEXT_HEADER),
    ] = None,
) -> CurrentModuleAccessRead:
    try:
        actor = actor_context_service.resolve(
            user_id=principal.user_id,
            requested_team_id=requested_team_id,
        )
    except TeamMembershipRequiredError:
        # An unassigned normal member remains authenticated but has no menu or
        # module capability.  This lets the PC show “未分配团队” instead of
        # turning a valid session into a fake login failure.
        return CurrentModuleAccessRead(
            module_codes=[],
            is_super_account=False,
            is_access_administrator=False,
        )
    return CurrentModuleAccessRead(
        module_codes=service.list_for_actor(actor),
        is_super_account=actor.is_super_account,
        is_access_administrator=actor.is_super_account,
    )


@router.get("/members", response_model=Page[AccessMemberRead])
def list_members(
    _actor: Annotated[ActorContext, Depends(get_super_account)],
    pagination: Annotated[PaginationParams, Depends()],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[AccessMemberRead]:
    members, total = service.list_members(
        offset=pagination.offset,
        limit=pagination.page_size,
        search=search.strip() if search else None,
    )
    return Page(
        items=[_member_read(member) for member in members],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/members/{user_id}", response_model=AccessMemberRead)
def get_member(
    user_id: UUID,
    _actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> AccessMemberRead:
    return _member_read(service.get_member(user_id))


@router.post("/members", response_model=AccessMemberRead, status_code=status.HTTP_201_CREATED)
def create_member(
    data: AccessMemberCreate,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> AccessMemberRead:
    return _member_read(
        service.create_member(
            data,
            actor=actor,
            request_id=get_request_id(request),
        ),
    )


@router.patch("/members/{user_id}", response_model=AccessMemberRead)
def update_member(
    user_id: UUID,
    data: AccessMemberUpdate,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> AccessMemberRead:
    return _member_read(
        service.update_member(
            user_id,
            data,
            actor=actor,
            request_id=get_request_id(request),
        ),
    )


@router.put("/members/{user_id}/team", response_model=AccessMemberRead)
def move_member_to_team(
    user_id: UUID,
    data: AccessMemberTeamUpdate,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> AccessMemberRead:
    """Assign a member to one Team, or remove it with ``team_id: null``."""

    return _member_read(
        service.move_member_to_team(
            user_id,
            data,
            actor=actor,
            request_id=get_request_id(request),
        ),
    )


@router.post("/members/{user_id}/password", response_model=AccessMemberRead)
def reset_member_password(
    user_id: UUID,
    data: AccessMemberPasswordReset,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> AccessMemberRead:
    return _member_read(
        service.reset_member_password(
            user_id,
            password=data.password.get_secret_value(),
            actor=actor,
            request_id=get_request_id(request),
        ),
    )


@router.post("/members/{user_id}/memberships", response_model=AccessMemberRead)
def create_membership(
    user_id: UUID,
    data: AccessMembershipCreate,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> AccessMemberRead:
    return _member_read(
        service.create_membership(
            user_id,
            data,
            actor=actor,
            request_id=get_request_id(request),
        ),
    )


@router.patch("/memberships/{membership_id}", response_model=AccessMemberRead)
def update_membership(
    membership_id: UUID,
    data: AccessMembershipUpdate,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> AccessMemberRead:
    return _member_read(
        service.update_membership(
            membership_id,
            data,
            actor=actor,
            request_id=get_request_id(request),
        ),
    )


@router.get("/teams", response_model=list[TeamRead])
def list_teams(
    _actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> list[TeamRead]:
    return [TeamRead.model_validate(team) for team in service.list_teams()]


@router.post("/teams", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_team(
    data: TeamCreate,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> TeamRead:
    return TeamRead.model_validate(
        service.create_team(
            data,
            actor=actor,
            request_id=get_request_id(request),
        ),
    )


@router.patch("/teams/{team_id}", response_model=TeamRead)
def update_team(
    team_id: UUID,
    data: TeamUpdate,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> TeamRead:
    return TeamRead.model_validate(
        service.update_team(
            team_id,
            data,
            actor=actor,
            request_id=get_request_id(request),
        ),
    )


@router.post("/teams/{team_id}/archive", response_model=TeamRead)
def archive_team(
    team_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> TeamRead:
    return TeamRead.model_validate(
        service.archive_team(
            team_id,
            actor=actor,
            request_id=get_request_id(request),
        ),
    )


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> None:
    service.delete_team(
        team_id,
        actor=actor,
        request_id=get_request_id(request),
    )


@router.get(
    "/teams/{team_id}/authorization",
    response_model=TeamAuthorizationRead,
)
def get_team_authorization(
    team_id: UUID,
    _actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> TeamAuthorizationRead:
    module_codes, device_ids, shop_ids = service.get_team_authorization(team_id)
    return TeamAuthorizationRead(
        team_id=team_id,
        module_codes=module_codes,
        device_ids=device_ids,
        shop_ids=shop_ids,
    )


@router.put(
    "/teams/{team_id}/authorization",
    response_model=TeamAuthorizationRead,
)
def update_team_authorization(
    team_id: UUID,
    data: TeamAuthorizationUpdate,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> TeamAuthorizationRead:
    module_codes, device_ids, shop_ids = service.update_team_authorization(
        team_id,
        data,
        actor=actor,
        request_id=get_request_id(request),
    )
    return TeamAuthorizationRead(
        team_id=team_id,
        module_codes=module_codes,
        device_ids=device_ids,
        shop_ids=shop_ids,
    )
