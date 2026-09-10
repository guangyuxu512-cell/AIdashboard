import httpx

from app.provisioning import WorkerProvisioningClient


def test_provisioning_resolves_device_identity_from_token_only() -> None:
    observed: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        observed["authorization"] = request.headers.get("Authorization")
        observed["device_id"] = request.headers.get("X-Device-ID")
        return httpx.Response(
            200,
            json={
                "device_id": "9b7644ca-fcfc-40e1-aab5-6d939d1267ca",
                "device_display_name": "PC-11",
                "device_enabled": True,
            },
        )

    result = WorkerProvisioningClient(
        transport=httpx.MockTransport(handler),
    ).test("https://control.example.test", "ccw_once")

    assert result.ok is True
    assert result.identity is not None
    assert result.identity.device_display_name == "PC-11"
    assert observed == {
        "authorization": "Bearer ccw_once",
        "device_id": None,
    }


def test_provisioning_distinguishes_invalid_token_and_server_errors() -> None:
    def unauthorized(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(401, json={"code": "WORKER_AUTHENTICATION_FAILED"})

    invalid = WorkerProvisioningClient(
        transport=httpx.MockTransport(unauthorized),
    ).test("https://control.example.test", "ccw_invalid")
    assert invalid.code == "TOKEN_INVALID"

    def unavailable(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    unreachable = WorkerProvisioningClient(
        transport=httpx.MockTransport(unavailable),
    ).test("https://control.example.test", "ccw_token")
    assert unreachable.code == "BACKEND_UNREACHABLE"


def test_provisioning_reports_html_health_as_a_health_format_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(
            200,
            text="<!doctype html><html><body>Frontend</body></html>",
            headers={"content-type": "text/html"},
        )

    result = WorkerProvisioningClient(
        transport=httpx.MockTransport(handler),
    ).test("https://control.example.test", "ccw_token")

    assert result.ok is False
    assert result.code == "HEALTH_RESPONSE_INVALID"
    assert result.message == "健康检查格式错误"


def test_provisioning_reports_malformed_device_payload_separately() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            text="<!doctype html><html><body>Frontend</body></html>",
            headers={"content-type": "text/html"},
        )

    result = WorkerProvisioningClient(
        transport=httpx.MockTransport(handler),
    ).test("https://control.example.test", "ccw_token")

    assert result.ok is False
    assert result.code == "PROVISIONING_RESPONSE_INVALID"
    assert result.message == "设备接入信息解析错误"
