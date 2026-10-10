"""Read-only persisted facts. No platform execution endpoint is implied."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import require_module_access
from app.modules.access.module_access import ModuleCode
from app.modules.product_selection.schemas import (
    SelectionObservationRead, SelectionSortDirection, SelectionSortField,
)
from app.modules.product_selection.service import ProductSelectionFactService
from app.shared.pagination import Page, PaginationParams


router = APIRouter(
    prefix="/api/v1/product-selection",
    tags=["product-selection"],
    responses={
        **COMMON_ERROR_RESPONSES,
        401: {"model": ErrorResponse, "description": "需要有效人员会话"},
        403: {"model": ErrorResponse, "description": "当前模块或团队不可访问"},
        404: {"model": ErrorResponse, "description": "候选来源不存在或不可访问"},
    },
)
get_selection_actor = require_module_access(ModuleCode.PRODUCT_SELECTION)


def get_selection_fact_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> ProductSelectionFactService:
    return ProductSelectionFactService(session)


@router.get("/candidates", response_model=Page[SelectionObservationRead])
def read_selection_candidates(
    actor: Annotated[ActorContext, Depends(get_selection_actor)],
    service: Annotated[ProductSelectionFactService, Depends(get_selection_fact_service)],
    pagination: Annotated[PaginationParams, Depends()],
    shop_id: Annotated[UUID | None, Query()] = None,
    source_scope_hash: Annotated[str | None, Query(pattern=r"^[a-f0-9]{64}$")] = None,
    search: Annotated[str | None, Query(max_length=255)] = None,
    sort_field: Annotated[SelectionSortField, Query()] = "checked_at",
    sort_direction: Annotated[SelectionSortDirection, Query()] = "desc",
) -> Page[SelectionObservationRead]:
    items, total = service.list_read(
        actor=actor, shop_id=shop_id, scope_hash=source_scope_hash,
        offset=pagination.offset, limit=pagination.page_size,
        sort=sort_field, descending=sort_direction == "desc", search=search,
    )
    return Page(items=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.get("/observations/{observation_id}", response_model=SelectionObservationRead)
def read_selection_observation(
    observation_id: UUID,
    actor: Annotated[ActorContext, Depends(get_selection_actor)],
    service: Annotated[ProductSelectionFactService, Depends(get_selection_fact_service)],
) -> SelectionObservationRead:
    return service.get_read(actor=actor, observation_id=observation_id)
