from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.ai_workbench.exceptions import (
    AiModelDefaultConflictError,
    AiModelIdentityConflictError,
    AiModelNotFoundError,
    AiModelProviderUnsupportedError,
)
from app.modules.ai_workbench.model_catalog_repository import AiModelRepository
from app.modules.ai_workbench.model_catalog_schemas import (
    AiModelCreate,
    AiModelUpdate,
)
from app.modules.ai_workbench.models import AiModel
from app.shared.identifiers import generate_id


SUPPORTED_AI_MODEL_PROVIDER_CODES = frozenset({"toapis"})


class AiModelCatalogService:
    def __init__(
        self,
        session: Session,
        repository: AiModelRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or AiModelRepository(session)

    def list_models(self) -> list[AiModel]:
        return self.repository.list_all()

    def list_available_models(self) -> list[AiModel]:
        return self.repository.list_enabled()

    def get_model(self, model_id: UUID) -> AiModel:
        model = self.repository.get(model_id)
        if model is None:
            raise AiModelNotFoundError()
        return model

    def create_model(self, data: AiModelCreate) -> AiModel:
        self._require_supported_provider(data.provider_code)
        models = self.repository.list_for_update()
        if any(
            model.provider_code == data.provider_code
            and model.model_code == data.model_code
            for model in models
        ):
            self.session.rollback()
            raise AiModelIdentityConflictError()
        if data.is_default:
            self._clear_default(models)
            self.session.flush()
        model = AiModel(
            model_id=generate_id(),
            display_name=data.display_name,
            model_code=data.model_code,
            provider_code=data.provider_code,
            enabled=data.enabled,
            is_default=data.is_default,
            capabilities=[capability.value for capability in data.capabilities],
            max_input_images=data.max_input_images,
            supported_sizes=[size.value for size in data.supported_sizes],
            supported_resolutions=[
                resolution.value for resolution in data.supported_resolutions
            ],
        )
        self.repository.add(model)
        self._commit()
        self.session.refresh(model)
        return model

    def update_model(
        self,
        model_id: UUID,
        data: AiModelUpdate,
    ) -> AiModel:
        models = self.repository.list_for_update()
        model = self._find_model(models, model_id)
        changes = data.model_dump(exclude_unset=True)
        next_enabled = changes.get("enabled", model.enabled)
        next_default = changes.get("is_default", model.is_default)
        if next_default and not next_enabled:
            self.session.rollback()
            raise AiModelDefaultConflictError()
        if model.is_default and (not next_enabled or not next_default):
            self.session.rollback()
            raise AiModelDefaultConflictError()
        if next_default:
            self._clear_default(models, except_model_id=model.model_id)
            self.session.flush()
        for field_name, value in changes.items():
            if field_name in {
                "capabilities",
                "supported_sizes",
                "supported_resolutions",
            }:
                value = [item.value for item in value]
            setattr(model, field_name, value)
        self._commit()
        self.session.refresh(model)
        return model

    def set_default_model(self, model_id: UUID) -> AiModel:
        models = self.repository.list_for_update()
        model = self._find_model(models, model_id)
        if not model.enabled:
            self.session.rollback()
            raise AiModelDefaultConflictError()
        self._clear_default(models, except_model_id=model.model_id)
        self.session.flush()
        model.is_default = True
        self._commit()
        self.session.refresh(model)
        return model

    @staticmethod
    def _clear_default(
        models: list[AiModel],
        *,
        except_model_id: UUID | None = None,
    ) -> None:
        for model in models:
            if model.model_id != except_model_id:
                model.is_default = False

    def _find_model(self, models: list[AiModel], model_id: UUID) -> AiModel:
        model = next((item for item in models if item.model_id == model_id), None)
        if model is None:
            self.session.rollback()
            raise AiModelNotFoundError()
        return model

    @staticmethod
    def _require_supported_provider(provider_code: str) -> None:
        if provider_code not in SUPPORTED_AI_MODEL_PROVIDER_CODES:
            raise AiModelProviderUnsupportedError()

    def _commit(self) -> None:
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise AiModelIdentityConflictError() from error
