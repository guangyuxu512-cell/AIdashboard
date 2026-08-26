from collections.abc import Iterator
from typing import Annotated, BinaryIO
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.assets.schemas import AssetRead
from app.modules.assets.service import AssetService
from app.shared.pagination import Page, PaginationParams


router = APIRouter(
    prefix="/api/v1/assets",
    tags=["assets"],
    responses={
        **COMMON_ERROR_RESPONSES,
        404: {"model": ErrorResponse, "description": "资产不存在"},
        409: {"model": ErrorResponse, "description": "资产正在被任务引用"},
    },
)


def get_asset_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> AssetService:
    return AssetService(session)


@router.post("", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
def upload_asset(
    file: Annotated[UploadFile, File()],
    service: Annotated[AssetService, Depends(get_asset_service)],
) -> AssetRead:
    return AssetRead.model_validate(
        service.upload(
            original_filename=file.filename,
            content_type=file.content_type,
            stream=file.file,
        ),
    )


@router.get("", response_model=Page[AssetRead])
def list_assets(
    service: Annotated[AssetService, Depends(get_asset_service)],
    pagination: Annotated[PaginationParams, Depends()],
    search: Annotated[str | None, Query(max_length=255)] = None,
) -> Page[AssetRead]:
    items, total = service.list(
        page=pagination.page,
        page_size=pagination.page_size,
        search=search,
    )
    return Page(
        items=[AssetRead.model_validate(asset) for asset in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{asset_id}/content", response_class=StreamingResponse)
def read_asset_content(
    asset_id: UUID,
    service: Annotated[AssetService, Depends(get_asset_service)],
) -> StreamingResponse:
    asset, content = service.get_content(asset_id)
    return asset_content_response(asset.content_type, asset.size_bytes, content)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    asset_id: UUID,
    service: Annotated[AssetService, Depends(get_asset_service)],
) -> Response:
    service.delete(asset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def asset_content_response(
    content_type: str,
    size_bytes: int,
    content: BinaryIO,
) -> StreamingResponse:
    def body() -> Iterator[bytes]:
        try:
            while chunk := content.read(64 * 1024):
                yield chunk
        finally:
            content.close()

    return StreamingResponse(
        body(),
        media_type=content_type,
        headers={
            "Content-Disposition": "inline",
            "Content-Length": str(size_bytes),
        },
    )
