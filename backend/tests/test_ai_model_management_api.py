import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient, Response

from app.core.database import get_database_session
from app.main import create_app
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import (
    get_actor_context,
    get_module_access_service,
    get_super_account,
)
from app.modules.access.enums import DataScope
from app.modules.access.exceptions import ModuleAccessDeniedError
from app.modules.access.module_access import ModuleCode
from app.modules.ai_workbench.model_catalog_api import (
    get_ai_model_catalog_authorized_actor,
    get_ai_model_catalog_service,
)
from app.modules.ai_workbench.model_catalog_schemas import (
    AiModelCreate,
    AiModelUpdate,
)
from app.modules.ai_workbench.models import AiModel
from tests.support import FakeSession


ADMIN = ActorContext(
    user_id=uuid4(),
    user_display_name="AI模型管理员",
    team_id=uuid4(),
    membership_id=uuid4(),
    role_code="access_admin",
    data_scope=DataScope.TEAM,
    is_super_account=True,
)
MEMBER = ActorContext(
    user_id=uuid4(),
    user_display_name="AI工作台成员",
    team_id=ADMIN.team_id,
    membership_id=uuid4(),
    role_code="member",
    data_scope=DataScope.TEAM,
)


def model_record(
    *,
    display_name: str = "GPT Image 2",
    model_code: str = "gpt-image-2",
    enabled: bool = True,
    is_default: bool = True,
) -> AiModel:
    now = datetime.now(UTC)
    return AiModel(
        model_id=uuid4(),
        display_name=display_name,
        model_code=model_code,
        provider_code="toapis",
        enabled=enabled,
        is_default=is_default,
        capabilities=["NORMAL_GENERATION", "STYLE_REPLICATION"],
        max_input_images=6,
        supported_sizes=["1:1", "3:4", "4:3", "16:9"],
        supported_resolutions=["1k", "2k", "4k"],
        created_at=now,
        updated_at=now,
    )


class ApiAiModelCatalogService:
    def __init__(self) -> None:
        self.models = [model_record()]

    def list_models(self) -> list[AiModel]:
        return list(self.models)

    def list_available_models(self) -> list[AiModel]:
        return [model for model in self.models if model.enabled]

    def get_model(self, model_id: UUID) -> AiModel:
        return next(model for model in self.models if model.model_id == model_id)

    def create_model(self, data: AiModelCreate) -> AiModel:
        model = model_record(
            display_name=data.display_name,
            model_code=data.model_code,
            enabled=data.enabled,
            is_default=data.is_default,
        )
        model.capabilities = [item.value for item in data.capabilities]
        model.max_input_images = data.max_input_images
        model.supported_sizes = [item.value for item in data.supported_sizes]
        model.supported_resolutions = [
            item.value for item in data.supported_resolutions
        ]
        self.models.append(model)
        return model

    def update_model(self, model_id: UUID, data: AiModelUpdate) -> AiModel:
        model = self.get_model(model_id)
        for field_name, value in data.model_dump(exclude_unset=True).items():
            if isinstance(value, list):
                value = [getattr(item, "value", item) for item in value]
            setattr(model, field_name, value)
        return model

    def set_default_model(self, model_id: UUID) -> AiModel:
        model = self.get_model(model_id)
        for item in self.models:
            item.is_default = item.model_id == model_id
        return model


class ApiModuleAccessService:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.checked: list[ModuleCode] = []

    def require_module_access(
        self,
        actor: ActorContext,
        module_code: ModuleCode,
    ) -> None:
        del actor
        self.checked.append(module_code)
        if not self.allowed:
            raise ModuleAccessDeniedError()


def request(
    method: str,
    path: str,
    *,
    service: ApiAiModelCatalogService,
    admin: ActorContext | None = None,
    catalog_actor: ActorContext | None = None,
    module_access: ApiModuleAccessService | None = None,
    **kwargs: object,
) -> Response:
    application = create_app()
    application.dependency_overrides[get_database_session] = lambda: FakeSession()
    application.dependency_overrides[get_ai_model_catalog_service] = lambda: service
    if admin is not None:
        application.dependency_overrides[get_super_account] = lambda: admin
    if catalog_actor is not None:
        application.dependency_overrides[
            get_ai_model_catalog_authorized_actor
        ] = lambda: catalog_actor
    if module_access is not None:
        application.dependency_overrides[get_actor_context] = lambda: MEMBER
        application.dependency_overrides[get_module_access_service] = (
            lambda: module_access
        )

    async def send() -> Response:
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def model_payload(*, model_code: str = "new-image-model") -> dict[str, object]:
    return {
        "display_name": "New Image Model",
        "model_code": model_code,
        "provider_code": "toapis",
        "enabled": True,
        "is_default": False,
        "capabilities": ["NORMAL_GENERATION"],
        "max_input_images": 2,
        "supported_sizes": ["1:1", "3:4"],
        "supported_resolutions": ["1k"],
    }


def test_routes_expose_admin_crud_without_hard_delete() -> None:
    paths = create_app().openapi()["paths"]

    assert {
        "/api/v1/ai-models",
        "/api/v1/ai-models/{model_id}",
        "/api/v1/ai-models/{model_id}/default",
        "/api/v1/ai-workbench/models",
    } <= set(paths)
    assert "delete" not in paths["/api/v1/ai-models/{model_id}"]


def test_access_administrator_can_manage_models() -> None:
    service = ApiAiModelCatalogService()

    listed = request("GET", "/api/v1/ai-models", service=service, admin=ADMIN)
    created = request(
        "POST",
        "/api/v1/ai-models",
        service=service,
        admin=ADMIN,
        json=model_payload(),
    )
    model_id = created.json()["model_id"]
    updated = request(
        "PATCH",
        f"/api/v1/ai-models/{model_id}",
        service=service,
        admin=ADMIN,
        json={"display_name": "Updated Image Model"},
    )
    defaulted = request(
        "POST",
        f"/api/v1/ai-models/{model_id}/default",
        service=service,
        admin=ADMIN,
    )

    assert listed.status_code == 200
    assert created.status_code == 201
    assert updated.json()["display_name"] == "Updated Image Model"
    assert defaulted.json()["is_default"] is True


def test_ordinary_member_cannot_manage_models() -> None:
    service = ApiAiModelCatalogService()
    application = create_app()
    application.dependency_overrides[get_actor_context] = lambda: MEMBER
    application.dependency_overrides[get_ai_model_catalog_service] = lambda: service

    async def send() -> Response:
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/api/v1/ai-models")

    response = asyncio.run(send())

    assert response.status_code == 403
    assert response.json()["code"] == "ACCESS_ADMINISTRATION_FORBIDDEN"


def test_business_catalog_requires_ai_workbench_and_hides_internal_provider() -> None:
    service = ApiAiModelCatalogService()
    service.models.append(
        model_record(
            display_name="Disabled Model",
            model_code="disabled-model",
            enabled=False,
            is_default=False,
        ),
    )
    allowed = ApiModuleAccessService(True)
    denied = ApiModuleAccessService(False)

    response = request(
        "GET",
        "/api/v1/ai-workbench/models",
        service=service,
        module_access=allowed,
    )
    forbidden = request(
        "GET",
        "/api/v1/ai-workbench/models",
        service=service,
        module_access=denied,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert allowed.checked == [ModuleCode.AI_WORKBENCH]
    assert forbidden.status_code == 403
    assert denied.checked == [ModuleCode.AI_WORKBENCH]
    assert set(response.json()[0]) == {
        "model_id",
        "model_code",
        "display_name",
        "capabilities",
        "max_input_images",
        "supported_sizes",
        "supported_resolutions",
        "is_default",
    }
    assert "provider_code" not in response.text
    assert "api_key" not in response.text
    assert "base_url" not in response.text
