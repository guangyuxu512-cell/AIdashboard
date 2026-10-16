"""Actual ASGI routing and WARNING streams, with no app lifespan, DB or network."""

import asyncio
import base64
import io
import json
import logging
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.database import get_database_session
from app.core.exceptions import install_exception_handlers
from app.core.logging.request import RequestLoggingMiddleware, request_logger
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import get_actor_context
from app.modules.access.enums import DataScope
from app.modules.sessions import api
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import ShopSessionPayloadInvalidError
from app.platforms.exceptions import PlatformAuthenticationInvalidError, PlatformRequestTimeoutError
from tests.test_shop_session_refresh_service import captured_payload, make_service


@pytest.fixture
def diagnostic_api(monkeypatch):
    resumed = []
    service, stored, storage = make_service(collection_resume=resumed.append)
    stored.status = ShopSessionStatus.VALID
    lease = service.acquire(stored.shop_id)
    actor = ActorContext(
        user_id=uuid4(), user_display_name="Synthetic operator", team_id=None,
        membership_id=None, role_code="super_account", data_scope=DataScope.ALL,
        is_super_account=True,
    )
    harness = SimpleNamespace(
        service=service, stored=stored, storage=storage, resumed=resumed,
        actor=actor, recheck_hook=lambda: None,
        body={
            "lease_id": str(lease.lease_id), "expected_version": lease.expected_version,
            "session_payload_base64": base64.b64encode(captured_payload()).decode(),
            "captured_at": datetime.now(UTC).isoformat(),
        },
        domain=io.StringIO(), access=io.StringIO(),
    )

    def resolve(**_kwargs):
        harness.recheck_hook()
        return harness.actor

    monkeypatch.setattr(api, "ActorContextService", lambda _session: SimpleNamespace(resolve=resolve))
    application = FastAPI()
    application.add_middleware(RequestLoggingMiddleware)
    install_exception_handlers(application)
    application.include_router(api.router)
    harness.application = application
    application.dependency_overrides[get_actor_context] = lambda: harness.actor
    application.dependency_overrides[api.get_shop_session_refresh_service] = lambda: service

    def no_database():
        raise AssertionError("No database access is allowed in this ASGI test")

    application.dependency_overrides[get_database_session] = no_database

    async def post(headers, query):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://asgi.test") as client:
            return await client.post(
                f"/api/v1/shops/{stored.shop_id}/session/refresh{query}",
                json=harness.body, headers=headers,
            )

    harness.post = lambda headers=None, query="": asyncio.run(post(headers or {}, query))
    domain_handler = logging.StreamHandler(harness.domain)
    access_handler = logging.StreamHandler(harness.access)
    domain_handler.setFormatter(logging.Formatter("%(message)s"))
    access_handler.setFormatter(logging.Formatter("%(message)s"))
    previous_level = api.logger.level
    api.logger.setLevel(logging.WARNING)
    api.logger.addHandler(domain_handler)
    request_logger.addHandler(access_handler)
    try:
        yield harness
    finally:
        api.logger.removeHandler(domain_handler)
        api.logger.setLevel(previous_level)
        request_logger.removeHandler(access_handler)
        domain_handler.close()
        access_handler.close()


def domain_records(harness):
    return [json.loads(line) for line in harness.domain.getvalue().splitlines()]


def test_request_injection_does_not_change_the_client_command_contract(diagnostic_api):
    document = diagnostic_api.application.openapi()
    command = document["components"]["schemas"]["CompleteShopSessionRefreshCommand"]
    assert set(command["required"]) == {
        "lease_id", "expected_version", "session_payload_base64", "captured_at",
    }
    operation = document["paths"]["/api/v1/shops/{shop_id}/session/refresh"]["post"]
    assert all(parameter["name"] != "request" for parameter in operation.get("parameters", []))


@pytest.mark.parametrize("stage", [
    "candidate_encoding", "candidate_json", "candidate_schema", "candidate_platform",
    "candidate_identity", "candidate_validation", "target_changed",
])
def test_asgi_stage_reaches_real_warning_and_original_response(stage, diagnostic_api, caplog):
    harness = diagnostic_api
    document = json.loads(captured_payload())
    if stage == "candidate_encoding":
        harness.body["session_payload_base64"] = "not base64!"
    elif stage == "candidate_json":
        harness.body["session_payload_base64"] = base64.b64encode(b"not json").decode()
    elif stage == "candidate_schema":
        harness.body["session_payload_base64"] = base64.b64encode(b'{"cookies": []}').decode()
    elif stage == "candidate_platform":
        document["platform"] = "pdd"
    elif stage == "candidate_identity":
        document["identity"]["platformShopId"] = "another-synthetic-shop"
    elif stage == "candidate_validation":
        harness.service.health_service.failure = ShopSessionPayloadInvalidError(details={
            "refresh_stage": stage, "validation_step": "cookie_merge",
        })
    else:
        harness.recheck_hook = lambda: setattr(harness.service.shop_repository.shop, "platform_shop_id", "changed")
    if stage in {"candidate_platform", "candidate_identity"}:
        harness.body["session_payload_base64"] = base64.b64encode(json.dumps(document).encode()).decode()
    request_id = str(uuid4())
    before = (harness.stored.version, harness.stored.status, harness.stored.payload_encrypted)
    response = harness.post({"X-Request-ID": request_id})
    body = response.json()
    records = domain_records(harness)
    assert response.status_code == 500
    assert body["code"] == "SHOP_SESSION_PAYLOAD_INVALID"
    assert body["message"] == ({
        "candidate_identity": "登录身份与目标店铺不匹配",
        "target_changed": "目标店铺身份已改变，请重新登录",
    }.get(stage, ShopSessionPayloadInvalidError.message))
    # 1.0.6 reads only this unchanged message; optional details do not require a new shell.
    assert len(records) == 1
    assert records[0] == {
        "event": "shop_session_refresh_payload_rejected",
        "error_code": body["code"], "request_id": request_id, **body["details"],
    }
    assert body["details"]["refresh_stage"] == stage
    assert response.headers["X-Request-ID"] == body["request_id"] == request_id
    access = json.loads(harness.access.getvalue())
    assert access["request_id"] == request_id
    assert "refresh_stage" not in access  # The global access-log contract remains unchanged.
    warnings = [record for record in caplog.records if record.name == api.logger.name]
    assert len(warnings) == 1 and warnings[0].levelno == logging.WARNING
    assert warnings[0].exc_info is None
    assert before == (harness.stored.version, harness.stored.status, harness.stored.payload_encrypted)
    assert harness.stored.refresh_lease_id is None
    assert harness.storage.payload is None and harness.resumed == []


@pytest.mark.parametrize("request_id", [
    None, "BFA4EB17-BBA5-4BBF-AD53-00EF350D63E2", "not-a-uuid-SYNTHETIC_PRIVATE_CANARY",
    "bfa4eb17bba54bbfad5300ef350d63e2", "{bfa4eb17-bba5-4bbf-ad53-00ef350d63e2}",
    "urn:uuid:bfa4eb17-bba5-4bbf-ad53-00ef350d63e2",
])
def test_only_uuid_shaped_request_id_enters_new_domain_log(request_id, diagnostic_api):
    harness = diagnostic_api
    harness.body["session_payload_base64"] = "not base64!"
    response = harness.post({"X-Request-ID": request_id} if request_id else {})
    record = domain_records(harness)[0]
    if request_id is None or request_id.startswith("BFA4"):
        assert record["request_id"] == response.json()["request_id"]
        assert str(UUID(record["request_id"])) == record["request_id"].lower()
    else:
        assert record["request_id"] == "unavailable"
        assert request_id not in harness.domain.getvalue()
        # Do not silently change the old response/access-log request-ID contract.
        assert response.json()["request_id"] == request_id


@pytest.mark.parametrize("details", [
    {"refresh_stage": "SYNTHETIC_PRIVATE_CANARY", "msg": "SYNTHETIC_PRIVATE_CANARY"},
    {"refresh_stage": "candidate_validation", "validation_step": "SYNTHETIC_PRIVATE_CANARY", "input": "SYNTHETIC_PRIVATE_CANARY"},
    {"refresh_stage": "candidate_schema", "schema_issues": [
        {"field": "SYNTHETIC_PRIVATE_CANARY", "type": "SYNTHETIC_PRIVATE_CANARY", "ctx": "SYNTHETIC_PRIVATE_CANARY"},
    ] * 5, "private": "SYNTHETIC_PRIVATE_CANARY"},
    ["SYNTHETIC_PRIVATE_CANARY"],
])
def test_arbitrary_details_and_schema_metadata_never_reach_warning_or_response(details, diagnostic_api, monkeypatch):
    harness = diagnostic_api

    def reject(*_args, **_kwargs):
        raise ShopSessionPayloadInvalidError(details=details)

    monkeypatch.setattr(harness.service, "complete", reject)
    response = harness.post()
    assert response.status_code == 500
    assert response.json()["message"] == ShopSessionPayloadInvalidError.message
    assert "SYNTHETIC_PRIVATE_CANARY" not in harness.domain.getvalue()
    assert "SYNTHETIC_PRIVATE_CANARY" not in response.text
    record = domain_records(harness)[0]
    assert set(record) <= {
        "event", "error_code", "request_id", "refresh_stage", "validation_step",
        "schema_issues", "schema_issues_truncated",
    }
    if "schema_issues" in record:
        assert len(record["schema_issues"]) <= 3
        assert record["schema_issues_truncated"] is True


def test_request_secrets_and_schema_input_do_not_enter_actual_log_streams(diagnostic_api):
    harness = diagnostic_api
    private = "SYNTHETIC_PRIVATE_CANARY"
    harness.body["session_payload_base64"] = base64.b64encode(json.dumps({
        "schema": "management-login.session.v1", "platform": "douyin",
        "cookies": [{"name": private, "value": private, "expirationDate": private}],
    }).encode()).decode()
    response = harness.post({"Cookie": f"synthetic={private}", "Authorization": f"Synthetic {private}"}, f"?private={private}")
    assert response.status_code == 500
    assert response.json()["details"]["schema_issues"] == [
        {"field": "cookies.expiration_date", "type": "float_parsing"},
    ]
    assert private not in response.text
    assert private not in harness.domain.getvalue() + harness.access.getvalue()


@pytest.mark.parametrize(("kind", "status"), [
    ("success", 200), ("permission", 403), ("version", 409), ("lease", 409),
    ("request_schema", 422), ("auth", 401), ("platform_timeout", 504),
])
def test_success_and_other_failures_do_not_create_payload_warning(kind, status, diagnostic_api):
    harness = diagnostic_api
    if kind == "permission":
        harness.actor = replace(harness.actor, is_super_account=False)
    elif kind == "version":
        harness.stored.version += 1
    elif kind == "lease":
        harness.body["lease_id"] = str(uuid4())
    elif kind == "request_schema":
        harness.body["captured_at"] = "not a timestamp"
    elif kind == "auth":
        harness.service.health_service.failure = PlatformAuthenticationInvalidError()
    elif kind == "platform_timeout":
        harness.service.health_service.failure = PlatformRequestTimeoutError()
    response = harness.post()
    assert response.status_code == status
    assert domain_records(harness) == []
    if kind == "success":
        assert response.json()["version"] == 4
        assert response.json()["used_cached_validation"] is False
        assert harness.resumed == [harness.stored.shop_id]
    else:
        assert harness.storage.payload is None and harness.resumed == []
