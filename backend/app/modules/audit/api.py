from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from pydantic import AwareDatetime, ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import get_super_account
from app.modules.audit.enums import AuditAction
from app.modules.audit.schemas import AuditLogCreatedRange, AuditLogRead
from app.modules.audit.service import AuditLogService
from app.shared.pagination import Page, PaginationParams


AUDIT_LOG_ERROR_RESPONSES = cast(
    dict[int | str, dict[str, Any]],
    COMMON_ERROR_RESPONSES.copy(),
)
AUDIT_LOG_ERROR_RESPONSES.update(
    {
        401: {"model": ErrorResponse, "description": "需要有效的管理端用户身份"},
        403: {"model": ErrorResponse, "description": "当前用户无权查看操作日志"},
        422: {"model": ErrorResponse, "description": "操作日志查询参数无效"},
    },
)


router = APIRouter(
    prefix="/api/v1/access-management/audit-logs",
    tags=["access-management"],
    responses=AUDIT_LOG_ERROR_RESPONSES,
)


def get_audit_log_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> AuditLogService:
    return AuditLogService(session)


def get_audit_log_created_range(
    created_from: Annotated[AwareDatetime | None, Query()] = None,
    created_to: Annotated[AwareDatetime | None, Query()] = None,
) -> AuditLogCreatedRange:
    try:
        return AuditLogCreatedRange(
            created_from=created_from,
            created_to=created_to,
        )
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error


@router.get("", response_model=Page[AuditLogRead])
def list_audit_logs(
    _actor: Annotated[ActorContext, Depends(get_super_account)],
    pagination: Annotated[PaginationParams, Depends()],
    created_range: Annotated[
        AuditLogCreatedRange,
        Depends(get_audit_log_created_range),
    ],
    service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    actor_user_id: Annotated[UUID | None, Query()] = None,
    action: Annotated[AuditAction | None, Query()] = None,
) -> Page[AuditLogRead]:
    return service.list_logs(
        page=pagination.page,
        page_size=pagination.page_size,
        created_from=created_range.created_from,
        created_to=created_range.created_to,
        actor_user_id=actor_user_id,
        action=action,
    )
