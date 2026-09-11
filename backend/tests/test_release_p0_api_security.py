from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient, Response

from app.core.database import get_database_session
from app.main import create_app
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import get_actor_context, get_module_access_service
from app.modules.access.enums import DataScope
from app.modules.access.exceptions import ModuleAccessDeniedError
from app.modules.access.module_access import ModuleCode
from app.modules.authentication.api import (
    get_management_onboarding_service,
    get_shop_authorized_actor as get_onboarding_shop_authorized_actor,
    router as onboarding_router,
)
from app.modules.authentication.schemas import (
    ManagementOnboardingResult,
    PddManagementLoginIdentityResult,
)
from app.modules.automation_apps.api import (
    get_catalog_service as get_automation_catalog_service,
    get_device_authorized_actor as get_automation_device_authorized_actor,
    get_service as get_automation_service,
    router as automation_router,
)
from app.modules.automation_apps.schemas import (
    AutomationApplicationConfigRead,
    YingdaoApplicationOptionRead,
)
from app.modules.credentials.api import (
    get_credential_service,
    get_shop_authorized_actor as get_credential_shop_authorized_actor,
    router as credentials_router,
)
from app.modules.credentials.enums import VerificationChannel
from app.modules.credentials.schemas import CredentialStatusRead
from app.modules.notifications.api import (
    get_notification_service,
    get_settings_authorized_actor,
    router as notifications_router,
)
from app.modules.sessions.api import (
    get_shop_authorized_actor as get_session_shop_authorized_actor,
    get_shop_session_refresh_service,
    router as sessions_router,
)
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.schemas import (
    ShopSessionMetadataRead,
    ShopSessionRefreshLeaseRead,
)
from app.modules.shops.api import (
    get_shop_authorized_actor,
    get_shop_service,
    router as shops_router,
)
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.schemas import ShopRead
from tests.support import FakeSession


SHOP_ID = uuid4()
CREDENTIAL_ID = uuid4()
CHANNEL_ID = uuid4()
ACTOR = ActorContext(
    user_id=uuid4(),
    user_display_name="Release P0 operator",
    team_id=uuid4(),
    membership_id=uuid4(),
    role_code="member",
    data_scope=DataScope.TEAM,
)


class ModuleAccessProbe:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.checked: list[ModuleCode] = []

    def require_module_access(
        self,
        actor: ActorContext,
        module_code: ModuleCode,
    ) -> None:
        assert actor == ACTOR
        self.checked.append(module_code)
        if not self.allowed:
            raise ModuleAccessDeniedError()


class ShopServiceStub:
    def remove(self, shop_id: UUID) -> None:
        assert shop_id == SHOP_ID


class SessionRefreshServiceStub:
    def acquire(self, shop_id: UUID) -> ShopSessionRefreshLeaseRead:
        assert shop_id == SHOP_ID
        return ShopSessionRefreshLeaseRead(
            shop_id=shop_id,
            lease_id=uuid4(),
            expected_version=1,
            expires_at=datetime.now(UTC),
        )


class CredentialServiceStub:
    def disable(self, credential_id: UUID) -> CredentialStatusRead:
        assert credential_id == CREDENTIAL_ID
        return credential_status()


class AutomationApplicationConfigServiceStub:
    def upsert(self, provider_code: str, app_id: str, data: object) -> AutomationApplicationConfigRead:
        assert provider_code == "yingdao"
        assert app_id == "release-p0-app"
        del data
        now = datetime.now(UTC)
        return AutomationApplicationConfigRead(
            config_id=uuid4(),
            provider_code=provider_code,
            app_id=app_id,
            schema_source="manual",
            input_schema={"fields": []},
            default_values={},
            version=1,
            created_at=now,
            updated_at=now,
        )


class AutomationApplicationCatalogServiceStub:
    def list_yingdao_application_options(
        self,
        *,
        actor: ActorContext,
    ) -> list[YingdaoApplicationOptionRead]:
        assert actor == ACTOR
        return [
            YingdaoApplicationOptionRead(
                app_id="release-p0-app",
                app_name="Release P0 应用",
            )
        ]


class NotificationServiceStub:
    def send_test(self, channel_id: UUID, *, now: datetime) -> None:
        assert channel_id == CHANNEL_ID
        assert now.tzinfo is not None


class ManagementOnboardingServiceStub:
    def complete(self, command: object) -> ManagementOnboardingResult:
        del command
        return ManagementOnboardingResult(
            shop=shop_read(),
            credential=credential_status(),
            session=ShopSessionMetadataRead(
                session_id=uuid4(),
                configured=True,
                status=ShopSessionStatus.CAPTURED,
                version=1,
                source_device_id=None,
                captured_at=datetime.now(UTC),
                validated_at=None,
                expires_at=None,
            ),
        )

    def verify_pdd_identity(
        self,
        command: object,
    ) -> PddManagementLoginIdentityResult:
        del command
        return PddManagementLoginIdentityResult(
            platform_shop_id="release-p0-pdd-shop",
            shop_display_name="Release P0 PDD Shop",
        )


def shop_read() -> ShopRead:
    now = datetime.now(UTC)
    return ShopRead(
        shop_id=SHOP_ID,
        display_name="Release P0 Shop",
        platform=ShopPlatform.DOUYIN,
        platform_shop_id="release-p0-shop",
        enabled=True,
        owner_user_id=None,
        note=None,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )


def credential_status() -> CredentialStatusRead:
    return CredentialStatusRead(
        credential_id=CREDENTIAL_ID,
        platform=ShopPlatform.DOUYIN,
        masked_identifier="138****8888",
        configured=True,
        enabled=True,
        preferred_verification_channel=VerificationChannel.MANUAL,
        updated_at=datetime.now(UTC),
    )


def configured_app() -> Any:
    application = create_app()
    application.dependency_overrides[get_database_session] = lambda: FakeSession()
    application.dependency_overrides[get_shop_service] = ShopServiceStub
    application.dependency_overrides[
        get_shop_session_refresh_service
    ] = SessionRefreshServiceStub
    application.dependency_overrides[get_credential_service] = CredentialServiceStub
    application.dependency_overrides[
        get_automation_service
    ] = AutomationApplicationConfigServiceStub
    application.dependency_overrides[
        get_automation_catalog_service
    ] = AutomationApplicationCatalogServiceStub
    application.dependency_overrides[get_notification_service] = NotificationServiceStub
    application.dependency_overrides[
        get_management_onboarding_service
    ] = ManagementOnboardingServiceStub
    return application


def request(
    method: str,
    path: str,
    *,
    module_access: ModuleAccessProbe | None = None,
    **kwargs: object,
) -> Response:
    application = configured_app()
    if module_access is not None:
        application.dependency_overrides[get_actor_context] = lambda: ACTOR
        application.dependency_overrides[get_module_access_service] = (
            lambda: module_access
        )

    async def send() -> Response:
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


MANAGEMENT_OPERATIONS = [
    ("DELETE", f"/api/v1/shops/{SHOP_ID}", {}, ModuleCode.SHOP),
    ("POST", f"/api/v1/shops/{SHOP_ID}/session/refresh-lease", {}, ModuleCode.SHOP),
    ("POST", f"/api/v1/credentials/{CREDENTIAL_ID}/disable", {}, ModuleCode.SHOP),
    (
        "PUT",
        "/api/v1/automation-app-configs/yingdao/release-p0-app",
        {"json": {"input_schema": {"fields": []}}},
        ModuleCode.DEVICE,
    ),
    ("POST", f"/api/v1/notification-channels/{CHANNEL_ID}/test", {}, ModuleCode.SETTINGS),
    (
        "POST",
        "/api/v1/shop-onboarding/complete",
        {
            "json": {
                "platform": "douyin",
                "platform_shop_id": "release-p0-shop",
                "shop_display_name": "Release P0 Shop",
                "login_identifier": "release-p0@example.com",
                "secret": "safe-test-secret",
                "session_payload_base64": "eA==",
                "session_captured_at": "2026-09-06T00:00:00Z",
            }
        },
        ModuleCode.SHOP,
    ),
    (
        "POST",
        "/api/v1/shop-onboarding/pdd/identity",
        {"json": {"session_payload_base64": "eA=="}},
        ModuleCode.SHOP,
    ),
]


@pytest.mark.parametrize(("method", "path", "kwargs", "_module_code"), MANAGEMENT_OPERATIONS)
def test_management_operations_require_human_authentication(
    method: str,
    path: str,
    kwargs: dict[str, object],
    _module_code: ModuleCode,
) -> None:
    response = request(method, path, **kwargs)

    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path", "kwargs", "module_code"), MANAGEMENT_OPERATIONS)
def test_management_operations_enforce_their_existing_module_access(
    method: str,
    path: str,
    kwargs: dict[str, object],
    module_code: ModuleCode,
) -> None:
    denied = ModuleAccessProbe(False)
    response = request(method, path, module_access=denied, **kwargs)

    assert response.status_code == 403
    assert denied.checked == [module_code]


@pytest.mark.parametrize(
    ("method", "path", "kwargs", "module_code", "status_code"),
    [
        (*MANAGEMENT_OPERATIONS[0], 204),
        (*MANAGEMENT_OPERATIONS[1], 201),
        (*MANAGEMENT_OPERATIONS[2], 200),
        (*MANAGEMENT_OPERATIONS[3], 200),
        (*MANAGEMENT_OPERATIONS[4], 200),
        (*MANAGEMENT_OPERATIONS[5], 201),
        (*MANAGEMENT_OPERATIONS[6], 200),
    ],
)
def test_authorized_module_users_can_complete_management_operations(
    method: str,
    path: str,
    kwargs: dict[str, object],
    module_code: ModuleCode,
    status_code: int,
) -> None:
    allowed = ModuleAccessProbe(True)
    response = request(method, path, module_access=allowed, **kwargs)

    assert response.status_code == status_code
    assert allowed.checked == [module_code]


def test_yingdao_application_catalog_requires_existing_device_module_access() -> None:
    path = "/api/v1/automation-app-configs/yingdao/applications"

    assert request("GET", path).status_code == 401

    denied = ModuleAccessProbe(False)
    denied_response = request("GET", path, module_access=denied)
    assert denied_response.status_code == 403
    assert denied.checked == [ModuleCode.DEVICE]

    allowed = ModuleAccessProbe(True)
    allowed_response = request("GET", path, module_access=allowed)
    assert allowed_response.status_code == 200
    assert allowed.checked == [ModuleCode.DEVICE]
    assert allowed_response.json() == [
        {"app_id": "release-p0-app", "app_name": "Release P0 应用"},
    ]


@pytest.mark.parametrize(
    ("router", "authorized_actor", "expected_count"),
    [
        (shops_router, get_shop_authorized_actor, 9),
        (sessions_router, get_session_shop_authorized_actor, 5),
        (credentials_router, get_credential_shop_authorized_actor, 4),
        (notifications_router, get_settings_authorized_actor, 4),
        (automation_router, get_automation_device_authorized_actor, 3),
        (onboarding_router, get_onboarding_shop_authorized_actor, 2),
    ],
)
def test_every_release_p0_management_handler_declares_its_guard(
    router: Any,
    authorized_actor: Any,
    expected_count: int,
) -> None:
    routes = [route for route in router.routes if isinstance(route, APIRoute)]

    assert len(routes) == expected_count
    assert all(
        any(dependency.call is authorized_actor for dependency in route.dependant.dependencies)
        for route in routes
    )
