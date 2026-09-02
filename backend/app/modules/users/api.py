from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import get_access_administrator
from app.modules.users.schemas import UserCreate, UserRead, UserUpdate
from app.modules.users.service import UserService
from app.shared.pagination import Page, PaginationParams


router = APIRouter(
    prefix="/api/v1/users",
    tags=["users"],
    responses={
        **COMMON_ERROR_RESPONSES,
        404: {"model": ErrorResponse, "description": "用户不存在"},
    },
)


def get_user_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> UserService:
    return UserService(session)


@router.get("", response_model=Page[UserRead])
def list_users(
    _actor: Annotated[ActorContext, Depends(get_access_administrator)],
    pagination: Annotated[PaginationParams, Depends()],
    service: Annotated[UserService, Depends(get_user_service)],
) -> Page[UserRead]:
    users, total = service.list(offset=pagination.offset, limit=pagination.page_size)
    return Page[UserRead](
        items=[UserRead.model_validate(user) for user in users],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: UUID,
    _actor: Annotated[ActorContext, Depends(get_access_administrator)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserRead:
    return UserRead.model_validate(service.get(user_id))


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    _actor: Annotated[ActorContext, Depends(get_access_administrator)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserRead:
    return UserRead.model_validate(service.create(data))


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: UUID,
    data: UserUpdate,
    _actor: Annotated[ActorContext, Depends(get_access_administrator)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserRead:
    return UserRead.model_validate(service.update(user_id, data))
