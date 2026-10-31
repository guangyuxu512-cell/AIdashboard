from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx

from app.config import WorkerSettings
from app.contracts import (
    ProviderInventoryReport,
    RuntimeEvent,
    SkillCapabilitySnapshot,
    TaskShopSession,
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

    async def read_precheck_shop_session(
        self, task_id: UUID, shop_id: UUID,
    ) -> TaskShopSession:
        """Read one authorized session into Worker memory over HTTPS only."""
        if self.client.base_url.scheme != "https":
            raise WorkerApiError(
                "PRECHECK_SESSION_HTTPS_REQUIRED",
                "Task session access requires HTTPS",
                0,
            )
        try:
            response = await self.client.post(
                f"/api/v1/worker/tasks/{task_id}/shop-sessions/{shop_id}",
                follow_redirects=False,
            )
        except httpx.HTTPError:
            raise WorkerApiError(
                "PRECHECK_SESSION_NETWORK_ERROR", "Task session request failed", 0,
            ) from None
        if not response.is_success:
            if response.status_code == 409:
                try:
                    body = response.json()
                except ValueError:
                    body = None
                if isinstance(body, dict) and body.get("code") == "PRECHECK_SESSION_AUTHORIZATION_BUSY":
                    # The caller may retry this acquisition; never retry a
                    # platform request or repeat it silently here.
                    raise WorkerApiError(
                        "PRECHECK_SESSION_AUTHORIZATION_BUSY",
                        "Task session authorization is temporarily busy",
                        response.status_code,
                    )
            # Do not reflect untrusted platform/server content into Worker logs.
            raise WorkerApiError(
                "PRECHECK_SESSION_UNAVAILABLE", "Task session is unavailable",
                response.status_code,
            )
        try:
            result = TaskShopSession.model_validate(response.json())
        except ValueError:
            raise WorkerApiError(
                "PRECHECK_SESSION_RESPONSE_INVALID", "Task session response is invalid",
                response.status_code,
            ) from None
        if result.shop_id != shop_id:
            raise WorkerApiError(
                "PRECHECK_SESSION_RESPONSE_INVALID", "Task session response is invalid",
                response.status_code,
            )
        if result.task_lease_until <= datetime.now(UTC):
            raise WorkerApiError(
                "PRECHECK_SESSION_LEASE_EXPIRED", "Task session lease has expired",
                response.status_code,
            )
        return result

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
