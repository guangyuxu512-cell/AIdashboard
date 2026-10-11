"""Authorized facts and manual-run contracts; no inferred platform mapping."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_database_session, get_session_factory
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import require_module_access
from app.modules.access.module_access import ModuleCode
from app.modules.product_selection.schemas import (
    SelectionObservationRead, SelectionSortDirection, SelectionSortField,
    SelectionCategoriesRead,
)
from app.modules.product_selection.service import ProductSelectionFactService
from app.shared.pagination import Page, PaginationParams
from app.modules.product_selection.run_contract import (
    SelectionCapabilitiesRead, SelectionRunCreate, SelectionRunRead, SelectionRunReceipt,
)
from app.modules.product_selection.run_service import SelectionRunService
from app.modules.product_selection.category_service import SelectionCategoryService


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


def get_selection_category_service() -> SelectionCategoryService:
    return SelectionCategoryService(get_session_factory())


@router.get("/categories", response_model=SelectionCategoriesRead)
def read_selection_categories(
    shop_id: UUID,
    actor: Annotated[ActorContext, Depends(get_selection_actor)],
    service: Annotated[SelectionCategoryService, Depends(get_selection_category_service)],
    session: Annotated[Session, Depends(get_database_session)],
) -> SelectionCategoriesRead:
    # Guard dependencies used this read-only transaction. Release it before
    # the category service starts its independent authorization / HTTP stages.
    session.rollback()
    return service.read(actor, shop_id)


def get_selection_fact_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> ProductSelectionFactService:
    return ProductSelectionFactService(session)


def get_selection_run_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> SelectionRunService:
    return SelectionRunService(session)


@router.get("/capabilities", response_model=SelectionCapabilitiesRead)
def read_selection_capabilities(
    actor: Annotated[ActorContext, Depends(get_selection_actor)],
    service: Annotated[SelectionRunService, Depends(get_selection_run_service)],
) -> SelectionCapabilitiesRead:
    service.facts._current_actor(actor)
    enabled = service.settings.product_selection_execution_enabled
    return SelectionCapabilitiesRead(execution_enabled=enabled, manual_execution_available=enabled,
                                     unavailable_reason=None if enabled else "EXECUTION_DISABLED")


@router.post("/runs", response_model=SelectionRunReceipt, status_code=202)
def submit_selection_run(
    command: SelectionRunCreate,
    actor: Annotated[ActorContext, Depends(get_selection_actor)],
    service: Annotated[SelectionRunService, Depends(get_selection_run_service)],
) -> SelectionRunReceipt:
    return service.submit(actor, command)


@router.get("/runs", response_model=Page[SelectionRunRead])
def read_selection_runs(
    actor: Annotated[ActorContext, Depends(get_selection_actor)],
    service: Annotated[SelectionRunService, Depends(get_selection_run_service)],
    pagination: Annotated[PaginationParams, Depends()],
    shop_id: Annotated[UUID | None, Query()] = None,
) -> Page[SelectionRunRead]:
    items, total = service.list(actor, shop_id=shop_id, offset=pagination.offset, limit=pagination.page_size)
    return Page(items=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.get("/runs/{run_id}", response_model=SelectionRunRead)
def read_selection_run(
    run_id: UUID,
    actor: Annotated[ActorContext, Depends(get_selection_actor)],
    service: Annotated[SelectionRunService, Depends(get_selection_run_service)],
) -> SelectionRunRead:
    return service.get(actor, run_id)


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
