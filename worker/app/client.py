from datetime import datetime
from typing import Any
from uuid import UUID

import httpx

from app.config import WorkerSettings
from app.contracts import WorkerTask


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
