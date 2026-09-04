from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.access.contracts import ActorContext, ManagedMember
from app.modules.access.dependencies import (
    get_access_administrator,
    get_access_management_service,
    get_actor_context,
    get_module_access_service,
)
from app.modules.access.schemas import (
    AccessMemberCreate,
    AccessMemberPasswordReset,
    AccessMemberRead,
    AccessMemberUpdate,
    AccessMembershipCreate,
    AccessMembershipRead,
    AccessMembershipUpdate,
    CurrentModuleAccessRead,
    TeamCreate,
    TeamRead,
    TeamUpdate,
)
from app.modules.access.roles import ACCESS_ADMIN_ROLE_CODE
from app.modules.access.service import AccessManagementService, ModuleAccessService
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
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    service: Annotated[ModuleAccessService, Depends(get_module_access_service)],
) -> CurrentModuleAccessRead:
    return CurrentModuleAccessRead(
        module_codes=service.list_for_membership(actor.membership_id),
        is_access_administrator=actor.role_code == ACCESS_ADMIN_ROLE_CODE,
    )


@router.get("/members", response_model=Page[AccessMemberRead])
def list_members(
    _actor: Annotated[ActorContext, Depends(get_access_administrator)],
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
    _actor: Annotated[ActorContext, Depends(get_access_administrator)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> AccessMemberRead:
    return _member_read(service.get_member(user_id))


@router.post("/members", response_model=AccessMemberRead, status_code=status.HTTP_201_CREATED)
def create_member(
    data: AccessMemberCreate,
    _actor: Annotated[ActorContext, Depends(get_access_administrator)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> AccessMemberRead:
    return _member_read(service.create_member(data))


@router.patch("/members/{user_id}", response_model=AccessMemberRead)
def update_member(
    user_id: UUID,
    data: AccessMemberUpdate,
    _actor: Annotated[ActorContext, Depends(get_access_administrator)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> AccessMemberRead:
    return _member_read(service.update_member(user_id, data))


@router.post("/members/{user_id}/password", response_model=AccessMemberRead)
def reset_member_password(
    user_id: UUID,
    data: AccessMemberPasswordReset,
    _actor: Annotated[ActorContext, Depends(get_access_administrator)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> AccessMemberRead:
    return _member_read(
        service.reset_member_password(
            user_id,
            password=data.password.get_secret_value(),
        ),
    )


@router.post("/members/{user_id}/memberships", response_model=AccessMemberRead)
def create_membership(
    user_id: UUID,
    data: AccessMembershipCreate,
    _actor: Annotated[ActorContext, Depends(get_access_administrator)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> AccessMemberRead:
    return _member_read(service.create_membership(user_id, data))


@router.patch("/memberships/{membership_id}", response_model=AccessMemberRead)
def update_membership(
    membership_id: UUID,
    data: AccessMembershipUpdate,
    _actor: Annotated[ActorContext, Depends(get_access_administrator)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> AccessMemberRead:
    return _member_read(service.update_membership(membership_id, data))


@router.get("/teams", response_model=list[TeamRead])
def list_teams(
    _actor: Annotated[ActorContext, Depends(get_access_administrator)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> list[TeamRead]:
    return [TeamRead.model_validate(team) for team in service.list_teams()]


@router.post("/teams", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_team(
    data: TeamCreate,
    _actor: Annotated[ActorContext, Depends(get_access_administrator)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> TeamRead:
    return TeamRead.model_validate(service.create_team(data))


@router.patch("/teams/{team_id}", response_model=TeamRead)
def update_team(
    team_id: UUID,
    data: TeamUpdate,
    _actor: Annotated[ActorContext, Depends(get_access_administrator)],
    service: Annotated[AccessManagementService, Depends(get_access_management_service)],
) -> TeamRead:
    return TeamRead.model_validate(service.update_team(team_id, data))
