import ssl
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx


@dataclass(frozen=True)
class WorkerProvisioningIdentity:
    device_id: UUID
    device_display_name: str
    device_enabled: bool


@dataclass(frozen=True)
class ConnectionTestResult:
    ok: bool
    code: str
    message: str
    identity: WorkerProvisioningIdentity | None = None


class WorkerProvisioningClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 8,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def test(self, server_url: str, token: str) -> ConnectionTestResult:
        base_url = server_url.strip().rstrip("/")
        if not base_url or not token.strip():
            return ConnectionTestResult(False, "CONFIG_INCOMPLETE", "请填写服务器地址和 Worker Token")
        try:
            parsed = httpx.URL(base_url)
        except (TypeError, ValueError):
            return ConnectionTestResult(False, "SERVER_URL_INVALID", "服务器地址格式无效")
        if parsed.scheme not in {"http", "https"} or not parsed.host:
            return ConnectionTestResult(False, "SERVER_URL_INVALID", "服务器地址必须是完整的 HTTP(S) URL")

        try:
            with httpx.Client(
                base_url=base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
                headers={"Authorization": f"Bearer {token.strip()}"},
            ) as client:
                health = client.get("/health")
                health.raise_for_status()
                try:
                    health_payload: Any = health.json()
                except ValueError:
                    return ConnectionTestResult(
                        False,
                        "HEALTH_RESPONSE_INVALID",
                        "健康检查格式错误",
                    )
                if not isinstance(health_payload, dict):
                    return ConnectionTestResult(
                        False,
                        "HEALTH_RESPONSE_INVALID",
                        "健康检查格式错误",
                    )
                if health_payload.get("status") != "ok":
                    return ConnectionTestResult(False, "BACKEND_UNHEALTHY", "服务器健康检查未通过")
                response = client.get("/api/v1/worker/provisioning")
                if response.status_code == 401:
                    return ConnectionTestResult(False, "TOKEN_INVALID", "Worker Token 无效或已撤销")
                response.raise_for_status()
                try:
                    payload: Any = response.json()
                    if not isinstance(payload, dict):
                        raise ValueError("Provisioning response is not an object")
                    identity = WorkerProvisioningIdentity(
                        device_id=UUID(str(payload["device_id"])),
                        device_display_name=str(payload["device_display_name"]),
                        device_enabled=bool(payload["device_enabled"]),
                    )
                except (KeyError, TypeError, ValueError):
                    return ConnectionTestResult(
                        False,
                        "PROVISIONING_RESPONSE_INVALID",
                        "设备接入信息解析错误",
                    )
        except httpx.TimeoutException:
            return ConnectionTestResult(False, "BACKEND_TIMEOUT", "连接服务器超时")
        except httpx.ConnectError as error:
            if _has_ssl_error(error):
                return ConnectionTestResult(False, "TLS_FAILED", "TLS 连接失败，请检查证书和服务器地址")
            return ConnectionTestResult(False, "BACKEND_UNREACHABLE", "服务器不可达")
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 401:
                return ConnectionTestResult(False, "TOKEN_INVALID", "Worker Token 无效或已撤销")
            return ConnectionTestResult(
                False,
                "BACKEND_ERROR",
                f"服务器返回 HTTP {error.response.status_code}",
            )
        except httpx.HTTPError:
            return ConnectionTestResult(False, "PROVISIONING_INVALID", "服务器返回的接入信息无法解析")
        return ConnectionTestResult(True, "OK", "连接成功，Worker Token 有效", identity)


def _has_ssl_error(error: BaseException) -> bool:
    current: BaseException | None = error
    while current is not None:
        if isinstance(current, ssl.SSLError):
            return True
        current = current.__cause__ or current.__context__
    return False
