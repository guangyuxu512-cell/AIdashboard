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
from app.modules.ai_workbench.schemas import (
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
