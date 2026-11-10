from datetime import datetime
from typing import Any
from uuid import UUID

import httpx

from app.config import WorkerSettings
from app.contracts import (
    ProviderInventoryReport,
    RuntimeEvent,
    SkillCapabilitySnapshot,
    WorkerTask,
)


class WorkerApiError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.status_code = status_code


class WorkerApiClient:
    def __init__(
        self,
        settings: WorkerSettings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            base_url=str(settings.server_url).rstrip("/"),
            timeout=settings.request_timeout_seconds,
            headers={
                "Authorization": (
                    f"Bearer {settings.device_token.get_secret_value()}"
                ),
                "X-Device-ID": str(settings.device_id),
            },
        )

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def heartbeat(
        self,
        *,
        worker_version: str,
        started_at: datetime,
    ) -> None:
        response = await self.client.post(
            "/api/v1/worker/heartbeat",
            json={
                "worker_version": worker_version,
                "started_at": started_at.isoformat(),
            },
        )
        self._raise_for_error(response)

    async def claim(self) -> WorkerTask | None:
        response = await self.client.post("/api/v1/worker/tasks/claim")
        if response.status_code == 204:
            return None
        self._raise_for_error(response)
        return WorkerTask.model_validate(response.json())

    async def download_task_asset(self, download_path: str) -> bytes:
        if not download_path.startswith("/api/v1/worker/tasks/"):
            raise WorkerApiError(
                "WORKER_ASSET_PATH_INVALID",
                "Worker asset download path is invalid",
                0,
            )
        response = await self.client.get(download_path)
        self._raise_for_error(response)
        return response.content

    async def fetch_capability_manifest(self) -> dict[str, str]:
        import json
        content = bytearray()
        async with self.client.stream("GET", "/api/v1/worker/capability-packages/manifest", follow_redirects=False) as response:
            if not response.is_success:
                raise WorkerApiError("CAPABILITY_MANIFEST_UNAVAILABLE", "Capability manifest unavailable", response.status_code)
            async for chunk in response.aiter_bytes():
                if len(content) + len(chunk) > 128 * 1024:
                    raise WorkerApiError("CAPABILITY_MANIFEST_TOO_LARGE", "Capability manifest exceeds limit", 0)
                content.extend(chunk)
        value = json.loads(content)
        if not isinstance(value, dict):
            raise WorkerApiError("CAPABILITY_MANIFEST_INVALID", "Capability manifest is invalid", 0)
        return value

    async def download_capability_package(self, digest: str, *, max_size: int) -> bytes:
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise WorkerApiError("CAPABILITY_DIGEST_INVALID", "Capability digest is invalid", 0)
        payload = bytearray()
        async with self.client.stream("GET", f"/api/v1/worker/capability-packages/blobs/{digest}", follow_redirects=False) as response:
            if not response.is_success:
                raise WorkerApiError("CAPABILITY_PACKAGE_UNAVAILABLE", "Capability package unavailable", response.status_code)
            async for chunk in response.aiter_bytes():
                if len(payload) + len(chunk) > max_size:
                    raise WorkerApiError("CAPABILITY_PACKAGE_TOO_LARGE", "Capability package exceeds limit", 0)
                payload.extend(chunk)
        return bytes(payload)

    async def report_rpa_inventory(self, payload: dict[str, Any]) -> None:
        response = await self.client.put("/api/v1/worker/rpa-shop-inventory", json=payload)
        self._raise_for_error(response)

    async def sign_precheck(self, task_id: UUID, *, cookie: str, user_agent: str) -> dict[str, str]:
        if self.settings.server_url.scheme != "https":
            raise WorkerApiError("PRECHECK_TLS_REQUIRED", "Precheck requires HTTPS", 0)
        response = await self.client.post(f"/api/v1/worker/tasks/{task_id}/precheck-sign",
                                          json={"cookie": cookie, "user_agent": user_agent})
        self._raise_for_error(response)
        body = response.json()
        if not isinstance(body, dict) or set(body) != {"url", "body"} or not all(isinstance(v, str) for v in body.values()):
            raise WorkerApiError("PRECHECK_SIGNER_INVALID", "Invalid signer response", 0)
        return body

    async def renew(self, task_id: UUID) -> None:
        response = await self.client.post(
            f"/api/v1/worker/tasks/{task_id}/renew",
        )
        self._raise_for_error(response)

    async def complete(self, task_id: UUID, result: dict[str, Any]) -> None:
        response = await self.client.post(
            f"/api/v1/worker/tasks/{task_id}/complete",
            json={"result": result},
        )
        self._raise_for_error(response)

    async def complete_precheck(
        self, task_id: UUID, *, status: str, result: dict[str, Any] | None,
        error_code: str | None, error_message: str | None,
    ) -> None:
        response = await self.client.post(
            f"/api/v1/worker/tasks/{task_id}/precheck-result",
            json={"status": status, "result": result,
                  "error_code": error_code, "error_message": error_message},
        )
        self._raise_for_error(response)

    async def report_provider_inventory(
        self,
        report: ProviderInventoryReport,
    ) -> None:
        response = await self.client.post(
            "/api/v1/worker/provider-inventory",
            json=report.model_dump(mode="json"),
        )
        self._raise_for_error(response)

    async def report_skill_capabilities(
        self,
        snapshot: SkillCapabilitySnapshot,
    ) -> None:
        response = await self.client.put(
            "/api/v1/worker/skill-capabilities",
            json=snapshot.model_dump(mode="json"),
        )
        self._raise_for_error(response)

    async def fail(
        self,
        task_id: UUID,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        response = await self.client.post(
            f"/api/v1/worker/tasks/{task_id}/fail",
            json={
                "error_code": error_code,
                "error_message": error_message,
            },
        )
        self._raise_for_error(response)

    async def report_task_events(
        self,
        task_id: UUID,
        events: list[RuntimeEvent],
    ) -> None:
        response = await self.client.post(
            f"/api/v1/worker/tasks/{task_id}/events",
            json={
                "events": [
                    event.model_dump(mode="json", exclude={"task_id"})
                    for event in events
                ],
            },
        )
        self._raise_for_error(response)

    @staticmethod
    def _raise_for_error(response: httpx.Response) -> None:
        if response.is_success:
            return
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        raise WorkerApiError(
            str(payload.get("code", "WORKER_API_ERROR")),
            str(payload.get("message", "Worker API request failed")),
            response.status_code,
        )
