import asyncio
import json
import logging
from typing import Any
from uuid import UUID, uuid4

from fastapi import Request
from httpx import ASGITransport, AsyncClient, Response

from app.core.exceptions import AppError
from app.core.logging.request import request_logger
from app.main import create_app
from app.modules.access.auth import get_human_principal
from app.modules.access.contracts import ActorContext, HumanPrincipal
from app.modules.access.dependencies import get_actor_context_service
from app.modules.access.enums import DataScope


USER_ID = uuid4()
TEAM_ID = uuid4()
MEMBERSHIP_ID = uuid4()


class CapturedRequestLogHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class RequestLogActorContextService:
    def resolve(
        self,
        *,
        user_id: UUID,
        requested_team_id: UUID | None,
    ) -> ActorContext:
        return ActorContext(
            user_id=user_id,
            user_display_name="日志测试用户",
            team_id=requested_team_id or TEAM_ID,
            membership_id=MEMBERSHIP_ID,
            role_code="member",
            data_scope=DataScope.TEAM,
        )


def _request(
    application: Any,
    method: str,
    path: str,
    *,
    raise_app_exceptions: bool = True,
    **kwargs: object,
) -> Response:
    async def send() -> Response:
        transport = ASGITransport(
            app=application,
            raise_app_exceptions=raise_app_exceptions,
        )
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def _capture_request_log() -> CapturedRequestLogHandler:
    handler = CapturedRequestLogHandler()
    request_logger.addHandler(handler)
    return handler


def _payload(handler: CapturedRequestLogHandler) -> dict[str, object]:
    assert len(handler.records) == 1
    return json.loads(handler.records[0].getMessage())


def test_request_log_records_success_and_returns_request_id() -> None:
    handler = _capture_request_log()
    try:
        response = _request(
            create_app(),
            "GET",
            "/health",
            headers={"X-Request-ID": "request-log-success"},
        )
    finally:
        request_logger.removeHandler(handler)

    payload = _payload(handler)
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "request-log-success"
    assert payload["request_id"] == "request-log-success"
    assert payload["method"] == "GET"
    assert payload["path"] == "/health"
    assert payload["status_code"] == 200
    assert isinstance(payload["latency"], int)
    assert payload["module"] == "system"


def test_request_log_records_error_code_for_handled_failure() -> None:
    class RequestLogFailure(AppError):
        code = "REQUEST_LOG_FAILURE"
        message = "请求日志失败测试"
        status_code = 409

    application = create_app()

    def fail() -> None:
        raise RequestLogFailure()

    application.add_api_route("/_test/request-log-failure", fail)
    handler = _capture_request_log()
    try:
        response = _request(application, "GET", "/_test/request-log-failure")
    finally:
        request_logger.removeHandler(handler)

    payload = _payload(handler)
    assert response.status_code == 409
    assert response.headers["X-Request-ID"] == response.json()["request_id"]
    assert payload["status_code"] == 409
    assert payload["error_code"] == "REQUEST_LOG_FAILURE"


def test_request_log_records_unexpected_failure_with_request_id() -> None:
    application = create_app()

    def fail() -> None:
        raise RuntimeError("unexpected failure")

    application.add_api_route("/_test/request-log-unexpected", fail)
    handler = _capture_request_log()
    try:
        response = _request(
            application,
            "GET",
            "/_test/request-log-unexpected",
            raise_app_exceptions=False,
        )
    finally:
        request_logger.removeHandler(handler)

    payload = _payload(handler)
    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == response.json()["request_id"]
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert payload["status_code"] == 500
    assert payload["error_code"] == "INTERNAL_ERROR"


def test_request_log_adds_resolved_user_and_team_context() -> None:
    application = create_app()
    application.dependency_overrides[get_human_principal] = lambda: HumanPrincipal(
        user_id=USER_ID,
        display_name="日志测试用户",
    )
    application.dependency_overrides[get_actor_context_service] = (
        RequestLogActorContextService
    )
    handler = _capture_request_log()
    try:
        response = _request(application, "GET", "/api/v1/access/me")
    finally:
        request_logger.removeHandler(handler)

    payload = _payload(handler)
    assert response.status_code == 200
    assert payload["user_id"] == str(USER_ID)
    assert payload["team_id"] == str(TEAM_ID)
    assert payload["module"] == "access"


def test_request_log_never_records_body_cookie_or_authorization() -> None:
    application = create_app()

    def accept_sensitive_input(request: Request) -> dict[str, bool]:
        del request
        return {"ok": True}

    application.add_api_route(
        "/_test/request-log-sensitive",
        accept_sensitive_input,
        methods=["POST"],
    )
    handler = _capture_request_log()
    try:
        response = _request(
            application,
            "POST",
            "/_test/request-log-sensitive",
            headers={
                "Authorization": "Bearer authorization-secret",
                "Cookie": "session=cookie-secret",
            },
            json={"password": "password-secret"},
        )
    finally:
        request_logger.removeHandler(handler)

    assert response.status_code == 200
    rendered = handler.records[0].getMessage()
    assert "authorization-secret" not in rendered
    assert "cookie-secret" not in rendered
    assert "password-secret" not in rendered
