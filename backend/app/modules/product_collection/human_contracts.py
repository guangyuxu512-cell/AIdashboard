"""Human-plane contracts for mobile product collection and the product library."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.product_collection.contracts import ProductCollectionRequestCreate


class ProductCollectionItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    item_id: UUID
    candidate_id: UUID | None
    platform: Literal["douyin", "pinduoduo"]
    source_product_id: str
    collection_mode: Literal["auto_gateway", "manual_return"]
    state: str
    library_product_id: UUID | None
    attempt_count: int
    last_error_code: str | None
    last_error_stage: str | None
    last_error_message: str | None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None


class ProductCollectionRequestRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    submission_key: UUID
    source_kind: Literal["manual", "selection_candidates"]
    target_group_id: UUID | None
    status: str
    item_count: int
    pending_count: int
    running_count: int
    succeeded_count: int
    failed_count: int
    canceled_count: int
    cancel_requested_at: datetime | None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None
    items: list[ProductCollectionItemRead] | None = None


class ProductCollectionRequestReceipt(BaseModel):
    """HTTP 202 receipt; persistence is not capture success."""

    request_id: UUID
    status: str
    item_count: int = Field(gt=0)
    reused: bool


class ProductLibraryGroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    group_id: UUID
    name: str


class ProductLibraryProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    product_id: UUID
    platform: Literal["douyin", "pinduoduo"]
    source_product_id: str
    group_id: UUID | None
    title: str | None
    source_url: str | None
    primary_image_url: str | None
    category_path: list[str] | None
    current_sale_price_cent: int | None
    currency: str | None
    adopted_version_id: UUID | None
    last_applied_capture_at: datetime | None
    last_ingested_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProductLibraryVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    version_id: UUID
    captured_at: datetime
    source_format_version: int
    cleaner_version: str
    raw_content_sha256: str
    uu_snapshot: dict
    price_evidence: dict


class ProductLibraryProductDetail(ProductLibraryProductRead):
    merchant_snapshot: dict | None
    versions: list[ProductLibraryVersionRead]
    latest_collection_state: str | None
    latest_collection_error_code: str | None


__all__ = [
    "ProductCollectionRequestCreate",
    "ProductCollectionItemRead",
    "ProductCollectionRequestRead",
    "ProductCollectionRequestReceipt",
    "ProductLibraryGroupRead",
    "ProductLibraryProductRead",
    "ProductLibraryProductDetail",
    "ProductLibraryVersionRead",
]
