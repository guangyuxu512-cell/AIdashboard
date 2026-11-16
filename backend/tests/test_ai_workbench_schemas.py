from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.ai_workbench.enums import (
    GenerationMode,
    GenerationSize,
    MaterialRole,
    OutputFormat,
    OutputRole,
)
from app.modules.ai_workbench.limits import (
    MAX_GENERATION_ITEMS,
    MAX_GENERATION_SELECTION_IDS,
)
from app.modules.ai_workbench.schemas import (
    BatchGenerationSubmit,
    GenerationItemArchiveRequest,
    GenerationRetryRequest,
    InstantGenerationSubmit,
    MaterialGroupAssetAttach,
    ProductMaterialGroupCreate,
    PromptTemplateCreate,
    PromptTemplateUpdate,
    TemplateGroupCreate,
)


def test_template_group_create_rejects_client_ownership() -> None:
    with pytest.raises(ValidationError):
        TemplateGroupCreate.model_validate(
            {
                "name": "商品主图",
                "mode": GenerationMode.NORMAL_GENERATION,
                "team_id": str(uuid4()),
            },
        )


def test_product_material_group_create_rejects_client_ownership() -> None:
    with pytest.raises(ValidationError):
        ProductMaterialGroupCreate.model_validate(
            {
                "name": "夏季新品",
                "created_by_user_id": str(uuid4()),
            },
        )


def test_prompt_template_normalizes_variables_and_uses_single_prompt() -> None:
    data = PromptTemplateCreate.model_validate(
        {
            "name": " 白底主图 ",
            "output_role": OutputRole.MAIN_IMAGE,
            "output_format": OutputFormat.SINGLE,
            "size": GenerationSize.SQUARE,
            "count": 2,
            "variables": [" product_name ", "selling_point", "product_name"],
            "prompt": " {product_name}，{selling_point} ",
        },
    )

    assert data.name == "白底主图"
    assert data.variables == ["product_name", "selling_point"]
    assert data.prompt == "{product_name}，{selling_point}"
    assert "negative_prompt" not in PromptTemplateCreate.model_fields


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {"negative_prompt": "不要文字"},
        {"output_role": OutputRole.DETAIL_IMAGE},
        {"template_group_id": str(uuid4())},
    ],
)
def test_prompt_update_rejects_frozen_or_internal_fields(
    invalid_payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        PromptTemplateUpdate.model_validate(invalid_payload)


def test_prompt_variables_reject_blank_and_excess_values() -> None:
    base = {
        "name": "详情",
        "output_role": OutputRole.DETAIL_IMAGE,
        "output_format": OutputFormat.COLLAGE_2X2,
        "size": GenerationSize.PORTRAIT,
        "count": 1,
        "prompt": "生成详情图",
    }

    with pytest.raises(ValidationError):
        PromptTemplateCreate.model_validate({**base, "variables": [" "]})
    with pytest.raises(ValidationError):
        PromptTemplateCreate.model_validate(
            {**base, "variables": [f"variable_{index}" for index in range(21)]},
        )


def test_public_asset_attach_rejects_ai_output_role() -> None:
    with pytest.raises(ValidationError):
        MaterialGroupAssetAttach(asset_id=uuid4(), role=MaterialRole.AI_OUTPUT)


def test_instant_generation_submit_freezes_supported_input_contract() -> None:
    product_asset_id = uuid4()
    reference_asset_id = uuid4()
    model_id = uuid4()
    data = InstantGenerationSubmit.model_validate(
        {
            "work_mode": "INSTANT",
            "submission_key": " stable-key ",
            "model_id": str(model_id),
            "mode": "STYLE_REPLICATION",
            "product_asset_ids": [str(product_asset_id)],
            "reference_asset_ids": [str(reference_asset_id)],
            "prompt": " 完整提示词 ",
            "output_format": "SINGLE",
            "size": "1:1",
            "count": 2,
        },
    )

    assert data.submission_key == "stable-key"
    assert data.prompt == "完整提示词"
    assert data.product_asset_ids == [product_asset_id]
    assert data.reference_asset_ids == [reference_asset_id]
    assert data.model_id == model_id
    assert data.compress_output_under_1000kb is False
    assert "output_role" not in InstantGenerationSubmit.model_fields
    for forbidden_field in (
        "team_id",
        "provider_id",
        "model_code",
        "external_task_id",
    ):
        with pytest.raises(ValidationError):
            InstantGenerationSubmit.model_validate(
                {
                    **data.model_dump(mode="json"),
                    forbidden_field: "forbidden",
                },
            )


def test_generation_submit_accepts_only_the_boolean_output_compression_policy() -> None:
    model_id = uuid4()
    product_asset_id = uuid4()
    instant = InstantGenerationSubmit.model_validate(
        {
            "work_mode": "INSTANT",
            "submission_key": "compression-enabled",
            "model_id": str(model_id),
            "mode": "NORMAL_GENERATION",
            "product_asset_ids": [str(product_asset_id)],
            "prompt": "完整提示词",
            "output_format": "SINGLE",
            "size": "1:1",
            "count": 1,
            "compress_output_under_1000kb": True,
        },
    )
    batch = BatchGenerationSubmit.model_validate(
        {
            "work_mode": "BATCH",
            "submission_key": "compression-default",
            "model_id": str(model_id),
            "mode": "NORMAL_GENERATION",
            "product_scope": "ALL_ENABLED",
            "template_source": "PRODUCT_CONFIGURED",
        },
    )

    assert instant.compress_output_under_1000kb is True
    assert batch.compress_output_under_1000kb is False
    with pytest.raises(ValidationError):
        InstantGenerationSubmit.model_validate(
            {
                **instant.model_dump(mode="json"),
                "compression_quality": 1,
            },
        )


def test_generation_submit_rejects_invalid_mode_inputs_and_duplicate_ids() -> None:
    asset_id = uuid4()
    base = {
        "work_mode": "INSTANT",
        "submission_key": "key",
        "model_id": str(uuid4()),
        "mode": "NORMAL_GENERATION",
        "product_asset_ids": [str(asset_id)],
        "prompt": "商品主图",
        "output_format": "SINGLE",
        "size": "1:1",
        "count": 1,
    }
    with pytest.raises(ValidationError):
        InstantGenerationSubmit.model_validate(
            {**base, "reference_asset_ids": [str(uuid4())]},
        )
    with pytest.raises(ValidationError):
        InstantGenerationSubmit.model_validate(
            {**base, "product_asset_ids": [str(asset_id), str(asset_id)]},
        )

    with pytest.raises(ValidationError):
        BatchGenerationSubmit.model_validate(
            {
                "work_mode": "BATCH",
                "submission_key": "key",
                "mode": "NORMAL_GENERATION",
                "product_scope": "SELECTED",
                "template_source": "PRODUCT_CONFIGURED",
            },
        )

    with pytest.raises(ValidationError):
        InstantGenerationSubmit.model_validate(
            {
                **base,
                "product_asset_ids": [
                    str(uuid4())
                    for _ in range(MAX_GENERATION_SELECTION_IDS + 1)
                ],
            },
        )

    with pytest.raises(ValidationError):
        BatchGenerationSubmit.model_validate(
            {
                "work_mode": "BATCH",
                "submission_key": "too-many-products",
                "mode": "NORMAL_GENERATION",
                "product_scope": "SELECTED",
                "selected_product_ids": [
                    str(uuid4())
                    for _ in range(MAX_GENERATION_SELECTION_IDS + 1)
                ],
                "template_source": "PRODUCT_CONFIGURED",
            },
        )
    with pytest.raises(ValidationError):
        BatchGenerationSubmit.model_validate(
            {
                "work_mode": "BATCH",
                "submission_key": "key",
                "mode": "NORMAL_GENERATION",
                "product_scope": "ALL_ENABLED",
                "template_source": "CURRENT_SELECTION",
            },
        )


def test_generation_retry_request_requires_unique_items() -> None:
    item_id = uuid4()
    with pytest.raises(ValidationError):
        GenerationRetryRequest.model_validate(
            {
                "items": [
                    {"item_id": str(item_id), "expected_attempt_count": 1},
                    {"item_id": str(item_id), "expected_attempt_count": 1},
                ],
            },
        )

    with pytest.raises(ValidationError):
        GenerationRetryRequest.model_validate(
            {
                "items": [
                    {
                        "item_id": str(uuid4()),
                        "expected_attempt_count": 1,
                    }
                    for _ in range(MAX_GENERATION_ITEMS + 1)
                ],
            },
        )

    with pytest.raises(ValidationError):
        GenerationItemArchiveRequest.model_validate(
            {
                "material_group_id": str(uuid4()),
                "team_id": str(uuid4()),
            },
        )
