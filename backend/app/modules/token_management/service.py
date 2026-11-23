import json
import re
from pathlib import Path

import httpx
from fastapi import HTTPException
from fastapi.responses import Response


_ID = r"[0-9a-f]{32}"
_SCOPED_RULES = (
    ("GET", r"api/v1/tokens"),
    ("GET", r"api/v1/tokens/permissions"),
    ("GET", r"api/v1/product-groups"),
    ("POST", r"api/v1/tokens"),
    ("PATCH", rf"api/v1/tokens/{_ID}"),
    ("DELETE", rf"api/v1/tokens/{_ID}"),
    ("POST", rf"api/v1/tokens/{_ID}/reveal"),
)
_COLLECTOR_RULES = (
    ("GET", r"collector-api/v1/admin/browsers"),
    ("POST", rf"collector-api/v1/admin/browsers/{_ID}/submit-token"),
    ("DELETE", rf"collector-api/v1/admin/browsers/{_ID}/submit-token"),
    ("POST", rf"collector-api/v1/admin/browsers/{_ID}/submit-token/reveal"),
    ("PATCH", rf"collector-api/v1/admin/browsers/{_ID}/submit-token/permissions"),
)
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def allowed_path(service: str, method: str, path: str) -> bool:
    rules = _SCOPED_RULES if service in {"product", "operations"} else (
        _COLLECTOR_RULES if service == "collector" else ()
    )
    return any(method == verb and re.fullmatch(pattern, path) for verb, pattern in rules)


class TokenManagementService:
    def __init__(self, origin: str | None, credentials_file: Path | None, *, transport=None):
        self._origin = origin
        self._credentials_file = credentials_file
        self._transport = transport

    def _credential(self, service: str) -> str:
        try:
            if self._credentials_file is None or self._credentials_file.stat().st_size > 32768:
                raise ValueError
            document = json.loads(self._credentials_file.read_text(encoding="utf-8"))
            value = document[service]
            if not isinstance(value, str) or not value or len(value) > 4096:
                raise ValueError
            if not value.isascii() or any(ord(c) < 33 or ord(c) > 126 for c in value):
                raise ValueError
            return value
        except (OSError, KeyError, TypeError, ValueError):
            raise HTTPException(503, "该服务暂不可用，请检查服务连接") from None

    async def forward(self, service: str, method: str, path: str, body: bytes) -> Response:
        if not allowed_path(service, method, path):
            raise HTTPException(404, "接口不存在")
        if not self._origin:
            raise HTTPException(503, "该服务暂不可用，请检查服务连接")
        credential = self._credential(service)
        url = f"{self._origin}/token-admin/_{service}/{path}"
        headers = {"Authorization": f"Bearer {credential}", "Accept": "application/json"}
        if body:
            headers["Content-Type"] = "application/json"
        try:
            async with httpx.AsyncClient(
                timeout=12.0, follow_redirects=False, trust_env=False, transport=self._transport,
            ) as client:
                async with client.stream(method, url, headers=headers, content=body) as upstream:
                    code = upstream.status_code
                    if code in (401, 403):
                        raise HTTPException(503, "该服务暂不可用，请检查服务连接")
                    if not 200 <= code < 300:
                        if not 400 <= code < 500:
                            code = 502
                        return Response(
                            content='{"detail":"服务请求未能完成"}', status_code=code,
                            media_type="application/json", headers={"Cache-Control": "no-store"},
                        )
                    if code == 204:
                        return Response(status_code=204, headers={"Cache-Control": "no-store"})
                    if "application/json" not in upstream.headers.get("content-type", "").lower():
                        raise HTTPException(502, "服务返回格式不正确")
                    data = bytearray()
                    async for chunk in upstream.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > _MAX_RESPONSE_BYTES:
                            raise HTTPException(502, "服务返回数据过大")
                    return Response(
                        content=bytes(data), status_code=code, media_type="application/json",
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
                    )
        except httpx.HTTPError:
            raise HTTPException(502, "该服务暂时无法连接") from None
