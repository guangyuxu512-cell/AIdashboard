from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.modules.ai_workbench.enums import (
    AiModelCapability,
    AiModelResolution,
    GenerationSize,
)
from app.modules.ai_workbench.exceptions import (
    AiModelDefaultConflictError,
    AiModelProviderUnsupportedError,
)
from app.modules.ai_workbench.model_catalog_schemas import (
    AiModelCreate,
    AiModelUpdate,
)
from app.modules.ai_workbench.model_catalog_service import AiModelCatalogService
from app.modules.ai_workbench.models import AiModel
from tests.support import FakeSession


class MemoryAiModelRepository:
    def __init__(self, models: list[AiModel] | None = None) -> None:
        self.models = models or []

    def list_all(self) -> list[AiModel]:
        return sorted(
            self.models,
            key=lambda model: (
                not model.is_default,
                model.display_name,
                str(model.model_id),
            ),
        )

    def list_enabled(self) -> list[AiModel]:
        return [model for model in self.list_all() if model.enabled]

    def list_for_update(self) -> list[AiModel]:
        return list(self.models)

    def get(self, model_id: UUID) -> AiModel | None:
        return next(
            (model for model in self.models if model.model_id == model_id),
            None,
        )

    def add(self, model: AiModel) -> None:
        self.models.append(model)


def model_record(
    *,
    display_name: str,
    model_code: str,
    enabled: bool = True,
    is_default: bool = False,
) -> AiModel:
    now = datetime.now(UTC)
    return AiModel(
        model_id=uuid4(),
        display_name=display_name,
        model_code=model_code,
        provider_code="toapis",
        enabled=enabled,
        is_default=is_default,
        capabilities=[
            AiModelCapability.NORMAL_GENERATION.value,
            AiModelCapability.STYLE_REPLICATION.value,
        ],
        max_input_images=6,
        supported_sizes=[size.value for size in GenerationSize],
        supported_resolutions=[resolution.value for resolution in AiModelResolution],
        created_at=now,
        updated_at=now,
    )


def create_input(
    *,
    display_name: str = "Next Image Model",
    model_code: str = "next-image-model",
    enabled: bool = True,
    is_default: bool = False,
) -> AiModelCreate:
    return AiModelCreate(
        display_name=display_name,
        model_code=model_code,
        provider_code="toapis",
        enabled=enabled,
        is_default=is_default,
        capabilities=[
            AiModelCapability.NORMAL_GENERATION,
            AiModelCapability.STYLE_REPLICATION,
        ],
        max_input_images=6,
        supported_sizes=list(GenerationSize),
        supported_resolutions=list(AiModelResolution),
    )


def service_with(
    models: list[AiModel],
) -> tuple[AiModelCatalogService, FakeSession, MemoryAiModelRepository]:
    session = FakeSession()
    repository = MemoryAiModelRepository(models)
    service = AiModelCatalogService(
        session,  # type: ignore[arg-type]
        repository=repository,  # type: ignore[arg-type]
    )
    return service, session, repository


def test_model_schema_keeps_capabilities_and_dimensions_bounded() -> None:
    data = create_input()

    assert data.capabilities == [
        AiModelCapability.NORMAL_GENERATION,
        AiModelCapability.STYLE_REPLICATION,
    ]
    assert data.supported_sizes == list(GenerationSize)
    assert data.supported_resolutions == list(AiModelResolution)

    with pytest.raises(ValidationError):
        create_input(is_default=True, enabled=False)
    with pytest.raises(ValidationError):
        AiModelUpdate.model_validate({"model_code": "changed-code"})
    with pytest.raises(ValidationError):
        AiModelUpdate.model_validate({"display_name": None})


def test_setting_default_switches_atomically_and_allows_disabling_previous() -> None:
    current = model_record(
        display_name="GPT Image 2",
        model_code="gpt-image-2",
        is_default=True,
    )
    candidate = model_record(
        display_name="Candidate",
        model_code="candidate",
    )
    service, session, _repository = service_with([current, candidate])

    result = service.set_default_model(candidate.model_id)

    assert result.is_default is True
    assert current.is_default is False
    assert session.commits == 1

    disabled = service.update_model(current.model_id, AiModelUpdate(enabled=False))
    assert disabled.enabled is False
    assert session.commits == 2


def test_default_model_cannot_be_disabled_or_cleared_directly() -> None:
    current = model_record(
        display_name="GPT Image 2",
        model_code="gpt-image-2",
        is_default=True,
    )
    service, session, _repository = service_with([current])

    with pytest.raises(AiModelDefaultConflictError):
        service.update_model(current.model_id, AiModelUpdate(enabled=False))
    with pytest.raises(AiModelDefaultConflictError):
        service.update_model(current.model_id, AiModelUpdate(is_default=False))

    assert current.enabled is True
    assert current.is_default is True
    assert session.commits == 0
    assert session.rollbacks == 2


def test_create_and_update_persist_catalog_capabilities() -> None:
    current = model_record(
        display_name="GPT Image 2",
        model_code="gpt-image-2",
        is_default=True,
    )
    service, session, repository = service_with([current])

    created = service.create_model(
        create_input(
            display_name="Normal Only",
            model_code="normal-only",
        ),
    )
    updated = service.update_model(
        created.model_id,
        AiModelUpdate(
            capabilities=[AiModelCapability.NORMAL_GENERATION],
            max_input_images=2,
            supported_sizes=[GenerationSize.SQUARE, GenerationSize.PORTRAIT],
            supported_resolutions=[AiModelResolution.ONE_K],
        ),
    )

    assert updated.capabilities == [AiModelCapability.NORMAL_GENERATION.value]
    assert updated.max_input_images == 2
    assert updated.supported_sizes == ["1:1", "3:4"]
    assert updated.supported_resolutions == ["1k"]
    assert repository.get(created.model_id) is updated
    assert session.commits == 2


def test_available_catalog_excludes_disabled_models() -> None:
    enabled = model_record(
        display_name="Enabled",
        model_code="enabled",
        is_default=True,
    )
    disabled = model_record(
        display_name="Disabled",
        model_code="disabled",
        enabled=False,
    )
    service, _session, _repository = service_with([enabled, disabled])

    assert service.list_available_models() == [enabled]


def test_only_current_provider_code_is_accepted() -> None:
    service, session, _repository = service_with([])
    data = create_input().model_copy(update={"provider_code": "unsupported"})

    with pytest.raises(AiModelProviderUnsupportedError):
        service.create_model(data)

    assert session.commits == 0
