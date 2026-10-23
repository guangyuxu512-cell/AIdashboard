"""Human APIs for durable phone collection requests and Team product facts."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.config import Settings, get_settings
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import require_module_access
from app.modules.access.module_access import ModuleCode
from app.modules.product_collection.contracts import ProductCollectionRequestCreate
from app.modules.product_collection.human_contracts import (
    ProductCollectionRequestRead,
    ProductCollectionRequestReceipt,
    ProductLibraryGroupRead,
    ProductLibraryProductDetail,
    ProductLibraryProductRead,
)
from app.modules.product_collection.human_service import ProductCollectionHumanService
from app.modules.product_collection.ports import GATEWAY_CAPTURE_MAX_ATTEMPTS
from app.shared.pagination import Page, PaginationParams


router = APIRouter(
    prefix="/api/v1",
    tags=["product-collection"],
    responses={
        **COMMON_ERROR_RESPONSES,
        401: {"model": ErrorResponse, "description": "需要有效人员会话"},
        403: {"model": ErrorResponse, "description": "当前商品库或团队不可访问"},
        404: {"model": ErrorResponse, "description": "资源不存在或当前不可访问"},
        409: {"model": ErrorResponse, "description": "提交标识或采集状态冲突"},
    },
)
get_product_library_actor = require_module_access(ModuleCode.PRODUCT_LIBRARY)


def get_human_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> ProductCollectionHumanService:
    return ProductCollectionHumanService(session)


@router.post(
    "/product-collection/requests",
    response_model=ProductCollectionRequestReceipt,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_product_collection_request(
    command: ProductCollectionRequestCreate,
    actor: Annotated[ActorContext, Depends(get_product_library_actor)],
    service: Annotated[ProductCollectionHumanService, Depends(get_human_service)],
) -> ProductCollectionRequestReceipt:
    return service.create_request(actor, command)


@router.get(
    "/product-collection/requests",
    response_model=Page[ProductCollectionRequestRead],
)
def list_product_collection_requests(
    actor: Annotated[ActorContext, Depends(get_product_library_actor)],
    service: Annotated[ProductCollectionHumanService, Depends(get_human_service)],
    pagination: Annotated[PaginationParams, Depends()],
) -> Page[ProductCollectionRequestRead]:
    items, total = service.list_requests(
        actor,
        offset=pagination.offset,
        limit=pagination.page_size,
    )
    return Page(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/product-collection/requests/{request_id}",
    response_model=ProductCollectionRequestRead,
)
def read_product_collection_request(
    request_id: UUID,
    actor: Annotated[ActorContext, Depends(get_product_library_actor)],
    service: Annotated[ProductCollectionHumanService, Depends(get_human_service)],
) -> ProductCollectionRequestRead:
    return service.get_request(actor, request_id)


@router.post(
    "/product-collection/requests/{request_id}/cancel",
    response_model=ProductCollectionRequestRead,
)
def cancel_product_collection_request(
    request_id: UUID,
    actor: Annotated[ActorContext, Depends(get_product_library_actor)],
    service: Annotated[ProductCollectionHumanService, Depends(get_human_service)],
) -> ProductCollectionRequestRead:
    return service.cancel_request(actor, request_id)


@router.post(
    "/product-collection/items/{item_id}/retry",
    response_model=ProductCollectionRequestRead,
)
def retry_product_collection_item(
    item_id: UUID,
    actor: Annotated[ActorContext, Depends(get_product_library_actor)],
    service: Annotated[ProductCollectionHumanService, Depends(get_human_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProductCollectionRequestRead:
    return service.retry_item(
        actor,
        item_id,
        max_delivery_attempts=settings.product_collection_delivery_max_attempts,
        max_capture_attempts=GATEWAY_CAPTURE_MAX_ATTEMPTS,
    )


@router.post(
    "/product-collection/items/{item_id}/recapture",
    response_model=ProductCollectionRequestRead,
)
def recapture_product_collection_item(
    item_id: UUID,
    actor: Annotated[ActorContext, Depends(get_product_library_actor)],
    service: Annotated[ProductCollectionHumanService, Depends(get_human_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProductCollectionRequestRead:
    return service.recapture_item(
        actor,
        item_id,
        gateway_id=settings.product_collection_gateway_id,
        max_capture_attempts=settings.product_collection_capture_max_attempts,
    )


@router.get(
    "/product-library/groups",
    response_model=list[ProductLibraryGroupRead],
)
def list_product_library_groups(
    actor: Annotated[ActorContext, Depends(get_product_library_actor)],
    service: Annotated[ProductCollectionHumanService, Depends(get_human_service)],
) -> list[ProductLibraryGroupRead]:
    return [ProductLibraryGroupRead.model_validate(item) for item in service.list_groups(actor)]


@router.get(
    "/product-library/products",
    response_model=Page[ProductLibraryProductRead],
)
def list_product_library_products(
    actor: Annotated[ActorContext, Depends(get_product_library_actor)],
    service: Annotated[ProductCollectionHumanService, Depends(get_human_service)],
    pagination: Annotated[PaginationParams, Depends()],
    search: Annotated[str | None, Query(max_length=200)] = None,
    group_id: UUID | None = None,
    ungrouped: bool = False,
) -> Page[ProductLibraryProductRead]:
    rows, total = service.list_products(
        actor,
        offset=pagination.offset,
        limit=pagination.page_size,
        search=search,
        group_id=group_id,
        ungrouped=ungrouped,
    )
    return Page(
        items=[ProductLibraryProductRead.model_validate(item) for item in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/product-library/products/{product_id}",
    response_model=ProductLibraryProductDetail,
)
def read_product_library_product(
    product_id: UUID,
    actor: Annotated[ActorContext, Depends(get_product_library_actor)],
    service: Annotated[ProductCollectionHumanService, Depends(get_human_service)],
) -> ProductLibraryProductDetail:
    return service.get_product(actor, product_id)
