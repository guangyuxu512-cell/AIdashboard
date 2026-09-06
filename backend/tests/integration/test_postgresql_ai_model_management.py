from uuid import uuid4

import pytest
from sqlalchemy import Engine, delete, inspect, select, text, update
from sqlalchemy.orm import Session

from app.core.database import get_database_engine
from app.modules.ai_workbench.enums import (
    AiModelCapability,
    AiModelResolution,
    GenerationSize,
)
from app.modules.ai_workbench.exceptions import AiModelDefaultConflictError
from app.modules.ai_workbench.model_catalog_schemas import (
    AiModelCreate,
    AiModelUpdate,
)
from app.modules.ai_workbench.model_catalog_service import AiModelCatalogService
from app.modules.ai_workbench.models import AiModel


pytestmark = pytest.mark.integration
FEATURE_DATABASE = "control_center_feat_ai_model_management"
INITIAL_MODEL_CODE = "gpt-image-2"


@pytest.fixture(scope="module")
def model_catalog_engine() -> Engine:
    engine = get_database_engine()
    if not engine.url.drivername.startswith("postgresql"):
        pytest.fail("AI model management integration tests require PostgreSQL")
    if engine.url.database != FEATURE_DATABASE:
        pytest.fail(
            f"AI model management tests only run against {FEATURE_DATABASE}",
        )
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == FEATURE_DATABASE
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "20260906_0031"
        )
    return engine


def test_ai_model_catalog_schema_and_initial_model(
    model_catalog_engine: Engine,
) -> None:
    inspector = inspect(model_catalog_engine)
    assert "ai_models" in inspector.get_table_names()
    assert {column["name"] for column in inspector.get_columns("ai_models")} == {
        "model_id",
        "display_name",
        "model_code",
        "provider_code",
        "enabled",
        "is_default",
        "capabilities",
        "max_input_images",
        "supported_sizes",
        "supported_resolutions",
        "created_at",
        "updated_at",
    }
    assert {
        "ck_ai_models_default_enabled",
        "ck_ai_models_capabilities_allowed",
        "ck_ai_models_supported_sizes_allowed",
        "ck_ai_models_supported_resolutions_allowed",
    } <= {constraint["name"] for constraint in inspector.get_check_constraints("ai_models")}
    assert {
        "uq_ai_models_enabled_default",
    } <= {index["name"] for index in inspector.get_indexes("ai_models")}

    with Session(model_catalog_engine) as session:
        model = session.scalar(
            select(AiModel).where(AiModel.model_code == INITIAL_MODEL_CODE),
        )
        assert model is not None
        assert model.display_name == "GPT Image 2"
        assert model.provider_code == "toapis"
        assert model.enabled is True
        assert model.is_default is True
        assert model.capabilities == [
            AiModelCapability.NORMAL_GENERATION.value,
            AiModelCapability.STYLE_REPLICATION.value,
        ]
        assert model.max_input_images == 6
        assert model.supported_sizes == [size.value for size in GenerationSize]
        assert model.supported_resolutions == [
            resolution.value for resolution in AiModelResolution
        ]


def test_ai_model_default_switch_and_enabled_catalog(
    model_catalog_engine: Engine,
) -> None:
    test_code = f"integration-model-{uuid4()}"
    created_id = None
    try:
        with Session(model_catalog_engine, expire_on_commit=False) as session:
            service = AiModelCatalogService(session)
            initial = next(
                model
                for model in service.list_models()
                if model.model_code == INITIAL_MODEL_CODE
            )
            created = service.create_model(
                AiModelCreate(
                    display_name="Integration Image Model",
                    model_code=test_code,
                    provider_code="toapis",
                    enabled=True,
                    is_default=False,
                    capabilities=[AiModelCapability.NORMAL_GENERATION],
                    max_input_images=2,
                    supported_sizes=[GenerationSize.SQUARE],
                    supported_resolutions=[AiModelResolution.ONE_K],
                ),
            )
            created_id = created.model_id
            service.set_default_model(created.model_id)

            defaults = [model for model in service.list_models() if model.is_default]
            assert defaults == [created]
            assert initial.is_default is False
            with pytest.raises(AiModelDefaultConflictError):
                service.update_model(created.model_id, AiModelUpdate(enabled=False))

            service.set_default_model(initial.model_id)
            service.update_model(created.model_id, AiModelUpdate(enabled=False))
            assert created not in service.list_available_models()
            assert [model for model in service.list_models() if model.is_default] == [
                initial,
            ]
    finally:
        if created_id is not None:
            with Session(model_catalog_engine) as cleanup:
                cleanup.execute(delete(AiModel).where(AiModel.model_id == created_id))
                cleanup.execute(
                    update(AiModel)
                    .where(AiModel.model_code == INITIAL_MODEL_CODE)
                    .values(enabled=True, is_default=True),
                )
                cleanup.commit()
