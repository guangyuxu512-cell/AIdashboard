"""Authorized database reads and explicit finite manual collection only."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import require_module_access
from app.modules.access.module_access import ModuleCode
from app.modules.product_data.exceptions import ProductDataQueryInvalidError
from app.modules.product_data.executor import execute_product_data_collection
from app.modules.product_data.schemas import (
    ProductDataCollectionRequest, ProductDataGenerationRead, ProductDataListRead,
    ProductDataMetricRange, ProductDataQuery,
)
from app.modules.product_data.service import ProductDataService
from app.modules.product_data.source import NativePeriod


router = APIRouter(prefix="/api/v1/product-data", tags=["product-data"], responses={
    **COMMON_ERROR_RESPONSES,
    401: {"model": ErrorResponse, "description": "需要有效人员会话"},
    403: {"model": ErrorResponse, "description": "模块或当前店铺无权访问"},
    409: {"model": ErrorResponse, "description": "采集冲突或会话需要验证"},
    503: {"model": ErrorResponse, "description": "环境未启用手动采集"},
})
get_product_data_actor = require_module_access(ModuleCode.SHOP)


def get_product_data_service(session: Annotated[Session, Depends(get_database_session)]):
    return ProductDataService(session)


def product_data_query(
    request: Request, period: NativePeriod, start_date: date, end_date: date,
    shop_id: UUID | None = None, product_id: str = "", product_name: str = "",
    sale_type: Literal["1"] = "1", content_type: Literal["1"] = "1",
    ranges: Annotated[str, Query(max_length=4096)] = "[]",
    page: int = 1, page_size: int = 20, sort_field: str | None = None,
    sort_direction: Literal["asc", "desc"] | None = None,
) -> ProductDataQuery:
    allowed = {"period", "start_date", "end_date", "shop_id", "product_id", "product_name", "sale_type", "content_type",
               "ranges", "page", "page_size", "sort_field", "sort_direction"}
    if set(request.query_params) - allowed or any(len(request.query_params.getlist(key)) != 1 for key in request.query_params):
        raise ProductDataQueryInvalidError()
    try:
        parsed = TypeAdapter(tuple[ProductDataMetricRange, ...]).validate_json(ranges)
        return ProductDataQuery(period=period, start_date=start_date, end_date=end_date, shop_id=shop_id,
            product_id=product_id, product_name=product_name, sale_type=sale_type, content_type=content_type,
            ranges=parsed, page=page, page_size=page_size, sort_field=sort_field, sort_direction=sort_direction)
    except ValidationError:
        raise ProductDataQueryInvalidError() from None


@router.get("", response_model=ProductDataListRead)
def list_product_data(
    actor: Annotated[ActorContext, Depends(get_product_data_actor)],
    service: Annotated[ProductDataService, Depends(get_product_data_service)],
    query: Annotated[ProductDataQuery, Depends(product_data_query)],
) -> ProductDataListRead:
    return service.list(actor, query)


@router.post("/collections", response_model=ProductDataGenerationRead, status_code=202)
def collect_product_data(
    command: ProductDataCollectionRequest, background: BackgroundTasks,
    actor: Annotated[ActorContext, Depends(get_product_data_actor)],
    service: Annotated[ProductDataService, Depends(get_product_data_service)],
) -> ProductDataGenerationRead:
    receipt, lease_id = service.request_collection(actor, command)
    if lease_id is not None:
        background.add_task(execute_product_data_collection, receipt.generation_id, lease_id)
    return receipt


@router.get("/collections/{generation_id}", response_model=ProductDataGenerationRead)
def read_product_data_collection(
    generation_id: UUID,
    actor: Annotated[ActorContext, Depends(get_product_data_actor)],
    service: Annotated[ProductDataService, Depends(get_product_data_service)],
) -> ProductDataGenerationRead:
    return service.read_generation(actor, generation_id)
