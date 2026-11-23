import json
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.core.config import Settings, get_settings
from app.modules.access.contracts import ActorContext
from app.modules.api_tokens.api import require_human_administrator
from app.modules.token_management.service import TokenManagementService, allowed_path


router = APIRouter(prefix="/api/v1/token-management", tags=["token-management"])
_MAX_REQUEST_BYTES = 65536


def get_token_management_service(settings: Annotated[Settings, Depends(get_settings)]) -> TokenManagementService:
    return TokenManagementService(settings.token_manager_proxy_origin, settings.token_manager_credentials_file)


def require_same_origin(request: Request, settings: Settings) -> None:
    origin = request.headers.get("origin", "")
    parsed = urlsplit(origin)
    host = request.headers.get("host", "").lower()
    allowed_schemes = {"https"} if settings.runtime_environment == "production" else {"http", "https"}
    if (parsed.scheme not in allowed_schemes or not host or parsed.netloc.lower() != host
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment
            or request.headers.get("sec-fetch-site") not in (None, "same-origin")):
        raise HTTPException(403, "请求来源无效")


@router.api_route("/{service}/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
async def manage(
    service: str,
    path: str,
    request: Request,
    _actor: Annotated[ActorContext, Depends(require_human_administrator)],
    settings: Annotated[Settings, Depends(get_settings)],
    bridge: Annotated[TokenManagementService, Depends(get_token_management_service)],
) -> Response:
    if request.url.query or not allowed_path(service, request.method, path):
        raise HTTPException(404, "接口不存在")
    if request.method != "GET":
        require_same_origin(request, settings)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > _MAX_REQUEST_BYTES:
            raise HTTPException(413, "请求过大")
    if body:
        if request.method == "GET" or request.headers.get("content-type", "").split(";", 1)[0].strip() != "application/json":
            raise HTTPException(415, "请求格式不正确")
        try:
            json.loads(body)
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(400, "请求格式不正确") from None
    return await bridge.forward(service, request.method, path, bytes(body))
