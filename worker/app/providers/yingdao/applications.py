from typing import Any

import httpx

from app.providers.yingdao.contracts import YingdaoApplication
from app.providers.yingdao.session import YingdaoSession, YingdaoSessionError


class YingdaoApplicationAdapter:
    def __init__(
        self,
        *,
        request_timeout_seconds: float = 10,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.request_timeout_seconds = request_timeout_seconds
        self.transport = transport

    async def list(self, session: YingdaoSession) -> list[YingdaoApplication]:
        payload = await self._get(session, "/api/v1/apps")
        raw_items = payload.get("items", payload.get("Items", []))
        if not isinstance(raw_items, list):
            raise YingdaoSessionError(
                "YINGDAO_APPLICATION_RESPONSE_INVALID",
                "影刀 6.3.6 云端应用响应缺少应用列表",
                provider_version=session.endpoint.process.version,
            )
        applications: list[YingdaoApplication] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            app_id = _text(item.get("appId") or item.get("AppId"))
            app_name = _text(item.get("appName") or item.get("AppName"))
            if not app_id or not app_name:
                continue
            applications.append(YingdaoApplication(
                app_id=app_id,
                app_name=app_name,
                version_id=_text(item.get("versionId") or item.get("VersionId")),
                updated_at=_text(item.get("updateTime") or item.get("UpdateTime")),
                app_type=_text(item.get("appType") or item.get("AppType")),
                group_id=_text(item.get("groupId") or item.get("GroupId")),
            ))
        return applications

    async def detail(self, session: YingdaoSession, app_id: str) -> dict[str, Any]:
        return await self._get(session, f"/api/v1/apps/{app_id}/detail")

    async def _get(self, session: YingdaoSession, path: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=self.request_timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.get(f"{session.endpoint.base_url}{path}")
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise YingdaoSessionError(
                "YINGDAO_APPLICATION_INTERFACE_UNREACHABLE",
                "影刀 6.3.6 云端应用接口请求失败",
                provider_version=session.endpoint.process.version,
            ) from error
        if not isinstance(payload, dict):
            raise YingdaoSessionError(
                "YINGDAO_APPLICATION_RESPONSE_INVALID",
                "影刀 6.3.6 云端应用响应无法解析",
                provider_version=session.endpoint.process.version,
            )
        code = payload.get("code")
        if code not in (None, 0):
            raise YingdaoSessionError(
                "YINGDAO_APPLICATION_INTERFACE_UNAVAILABLE",
                f"影刀 6.3.6 云端应用接口返回错误码 {code}",
                provider_version=session.endpoint.process.version,
            )
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            raise YingdaoSessionError(
                "YINGDAO_APPLICATION_RESPONSE_INVALID",
                "影刀 6.3.6 云端应用响应数据无效",
                provider_version=session.endpoint.process.version,
            )
        return data


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
