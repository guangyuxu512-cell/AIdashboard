from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions.errors import AppError


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict[str, Any] | list[Any] | None = None


COMMON_ERROR_RESPONSES: dict[int, dict[str, Any]] = {
    422: {"model": ErrorResponse, "description": "请求参数校验失败"},
    500: {"model": ErrorResponse, "description": "服务器或数据库操作失败"},
}


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID") or str(uuid4())


def install_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(AppError)
    async def handle_app_error(request: Request, error: AppError) -> JSONResponse:
        request_id = _request_id(request)
        response = ErrorResponse(
            code=error.code,
            message=error.message,
            request_id=request_id,
            details=error.details,
        )
        return JSONResponse(
            status_code=error.status_code,
            content=response.model_dump(mode="json"),
            headers={"X-Request-ID": request_id},
        )

    @application.exception_handler(SQLAlchemyError)
    async def handle_database_error(
        request: Request,
        error: SQLAlchemyError,
    ) -> JSONResponse:
        request_id = _request_id(request)
        response = ErrorResponse(
            code="DATABASE_OPERATION_FAILED",
            message="数据库操作失败",
            request_id=request_id,
        )
        return JSONResponse(
            status_code=500,
            content=response.model_dump(mode="json"),
            headers={"X-Request-ID": request_id},
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        request_id = _request_id(request)
        response = ErrorResponse(
            code="VALIDATION_ERROR",
            message="请求参数校验失败",
            request_id=request_id,
            details=jsonable_encoder(error.errors()),
        )
        return JSONResponse(
            status_code=422,
            content=response.model_dump(mode="json"),
            headers={"X-Request-ID": request_id},
        )
