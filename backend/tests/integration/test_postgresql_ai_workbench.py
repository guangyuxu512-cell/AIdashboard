from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete, inspect, select, text
from sqlalchemy.orm import Session

from app.core.database import get_database_engine
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.models import Team
from app.modules.ai_workbench.enums import (
    GenerationMode,
    GenerationSize,
    MaterialRole,
    OutputFormat,
    OutputRole,
)
from app.modules.ai_workbench.exceptions import (
    ProductMaterialGroupNotFoundError,
    TemplateGroupInUseError,
)
from app.modules.ai_workbench.models import (
    MaterialGroupAsset,
    MaterialGroupTemplateBinding,
    ProductMaterialGroup,
    PromptTemplate,
    TemplateGroup,
)
from app.modules.ai_workbench.repository import ProductMaterialGroupRepository
from app.modules.ai_workbench.schemas import (
    MaterialGroupAssetAttach,
    ProductMaterialGroupCreate,
    ProductMaterialGroupUpdate,
    PromptTemplateCreate,
    TemplateBindingReplace,
    TemplateGroupCreate,
    TemplateGroupUpdate,
)
from app.modules.ai_workbench.service import AiWorkbenchService
from app.modules.assets.enums import AssetMediaType, AssetSourceType
from app.modules.assets.exceptions import AssetNotFoundError
from app.modules.assets.models import Asset
from app.modules.users.models import User


pytestmark = pytest.mark.integration
FEATURE_DATABASE = "control_center_feat_ai_generation"
AI_TABLES = {
    "template_groups",
    "prompt_templates",
    "product_material_groups",
    "material_group_assets",
    "material_group_template_bindings",
}


@pytest.fixture(scope="module")
def ai_postgresql_engine() -> Engine:
    engine = get_database_engine()
    if not engine.url.drivername.startswith("postgresql"):
        pytest.fail("AI integration tests require PostgreSQL")
    if engine.url.database != FEATURE_DATABASE:
        pytest.fail(f"AI integration tests only run against {FEATURE_DATABASE}")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == FEATURE_DATABASE
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "20260903_0027"
        )
    assert AI_TABLES <= set(inspect(engine).get_table_names())
    return engine


def actor(
    *,
    user_id: UUID,
    team_id: UUID,
    scope: DataScope,
) -> ActorContext:
    return ActorContext(
        user_id=user_id,
        user_display_name=f"AI Integration {scope.value}",
        team_id=team_id,
        membership_id=uuid4(),
        role_code="member",
        data_scope=scope,
    )


def asset(
    *,
    asset_id: UUID,
    team_id: UUID,
    created_by_user_id: UUID,
    filename: str,
) -> Asset:
    return Asset(
        asset_id=asset_id,
        team_id=team_id,
        created_by_user_id=created_by_user_id,
        original_filename=filename,
        storage_key=f"stage-2a1-ai/{asset_id}.png",
        media_type=AssetMediaType.IMAGE.value,
        source_type=AssetSourceType.UPLOAD.value,
        content_type="image/png",
        size_bytes=64,
        sha256="a" * 64,
    )


class FailingProductMaterialGroupRepository(ProductMaterialGroupRepository):
    def add_bindings(
        self,
        bindings: Sequence[MaterialGroupTemplateBinding],
    ) -> None:
        super().add_bindings(bindings)
        self.session.flush()
        raise RuntimeError("forced binding transaction failure")


def test_ai_workbench_schema_constraints(ai_postgresql_engine: Engine) -> None:
    inspector = inspect(ai_postgresql_engine)
    assert AI_TABLES <= set(inspector.get_table_names())

    binding_foreign_keys = {
        item["name"]: item
        for item in inspector.get_foreign_keys("material_group_template_bindings")
    }
    assert binding_foreign_keys[
        "fk_material_template_bindings_template_group"
    ]["options"]["ondelete"] == "RESTRICT"
    assert binding_foreign_keys[
        "fk_material_template_bindings_material_group"
    ]["options"]["ondelete"] == "RESTRICT"
    asset_foreign_keys = {
        item["name"]: item
        for item in inspector.get_foreign_keys("material_group_assets")
    }
    assert asset_foreign_keys["fk_material_group_assets_asset"]["options"][
        "ondelete"
    ] == "RESTRICT"
    assert {
        "ix_template_groups_team_created_group",
        "ix_template_groups_team_creator_created_group",
    } <= {item["name"] for item in inspector.get_indexes("template_groups")}
    assert {
        "ix_product_material_groups_team_created_group",
        "ix_product_material_groups_team_creator_created_group",
    } <= {
        item["name"]
        for item in inspector.get_indexes("product_material_groups")
    }


def test_ai_workbench_postgresql_scope_relations_and_transactions(
    ai_postgresql_engine: Engine,
) -> None:
    team_a_id, team_b_id = uuid4(), uuid4()
    user_a1_id, user_a2_id, user_b_id, all_user_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    same_team_asset_id, cross_team_asset_id = uuid4(), uuid4()
    team_ids = {team_a_id, team_b_id}
    user_ids = {user_a1_id, user_a2_id, user_b_id, all_user_id}
    asset_ids = {same_team_asset_id, cross_team_asset_id}

    try:
        with Session(ai_postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    Team(team_id=team_a_id, name="stage-2a1 AI 团队 A", enabled=True),
                    Team(team_id=team_b_id, name="stage-2a1 AI 团队 B", enabled=True),
                    User(user_id=user_a1_id, display_name="stage-2a1 AI 用户 A1", enabled=True),
                    User(user_id=user_a2_id, display_name="stage-2a1 AI 用户 A2", enabled=True),
                    User(user_id=user_b_id, display_name="stage-2a1 AI 用户 B", enabled=True),
                    User(user_id=all_user_id, display_name="stage-2a1 AI 全局用户", enabled=True),
                ],
            )
            session.commit()
            session.add_all(
                [
                    asset(
                        asset_id=same_team_asset_id,
                        team_id=team_a_id,
                        created_by_user_id=user_a2_id,
                        filename="same-team.png",
                    ),
                    asset(
                        asset_id=cross_team_asset_id,
                        team_id=team_b_id,
                        created_by_user_id=user_b_id,
                        filename="cross-team.png",
                    ),
                ],
            )
            session.commit()

            self_a1 = actor(
                user_id=user_a1_id,
                team_id=team_a_id,
                scope=DataScope.SELF,
            )
            self_a2 = actor(
                user_id=user_a2_id,
                team_id=team_a_id,
                scope=DataScope.SELF,
            )
            team_a = actor(
                user_id=user_a1_id,
                team_id=team_a_id,
                scope=DataScope.TEAM,
            )
            team_b = actor(
                user_id=user_b_id,
                team_id=team_b_id,
                scope=DataScope.TEAM,
            )
            all_from_a = actor(
                user_id=all_user_id,
                team_id=team_a_id,
                scope=DataScope.ALL,
            )
            service = AiWorkbenchService(session)

            normal_a1 = service.create_template_group(
                self_a1,
                TemplateGroupCreate(
                    name="stage-2a1 AI Normal A1",
                    mode=GenerationMode.NORMAL_GENERATION,
                ),
            )
            normal_a2 = service.create_template_group(
                self_a2,
                TemplateGroupCreate(
                    name="stage-2a1 AI Normal A2",
                    mode=GenerationMode.NORMAL_GENERATION,
                ),
            )
            normal_b = service.create_template_group(
                team_b,
                TemplateGroupCreate(
                    name="stage-2a1 AI Normal B",
                    mode=GenerationMode.NORMAL_GENERATION,
                ),
            )
            style_a = service.create_template_group(
                self_a1,
                TemplateGroupCreate(
                    name="stage-2a1 AI Style A",
                    mode=GenerationMode.STYLE_REPLICATION,
                ),
            )

            self_items, self_total = service.list_template_groups(
                actor=self_a1,
                page=1,
                page_size=20,
                search="stage-2a1 AI",
                mode=None,
                enabled=None,
            )
            assert self_total == 2
            assert {item.template_group_id for item in self_items} == {
                normal_a1.template_group_id,
                style_a.template_group_id,
            }
            team_items, team_total = service.list_template_groups(
                actor=team_a,
                page=1,
                page_size=2,
                search="stage-2a1 AI Normal",
                mode=GenerationMode.NORMAL_GENERATION,
                enabled=True,
            )
            assert team_total == 2
            assert len(team_items) == 2
            all_items, all_total = service.list_template_groups(
                actor=all_from_a,
                page=1,
                page_size=20,
                search="stage-2a1 AI Normal",
                mode=GenerationMode.NORMAL_GENERATION,
                enabled=None,
            )
            assert all_total == 3
            assert normal_b.template_group_id in {
                item.template_group_id for item in all_items
            }
            assert (
                service.get_template_group(all_from_a, normal_b.template_group_id)
                .template_group_id
                == normal_b.template_group_id
            )

            service.create_prompt_template(
                self_a1,
                normal_a1.template_group_id,
                PromptTemplateCreate(
                    name="详情",
                    output_role=OutputRole.DETAIL_IMAGE,
                    output_format=OutputFormat.COLLAGE_2X2,
                    size=GenerationSize.PORTRAIT,
                    count=2,
                    variables=[" product_name ", "product_name"],
                    prompt="{product_name}",
                ),
            )
            normal_a1 = service.create_prompt_template(
                self_a1,
                normal_a1.template_group_id,
                PromptTemplateCreate(
                    name="主图",
                    output_role=OutputRole.MAIN_IMAGE,
                    output_format=OutputFormat.SINGLE,
                    size=GenerationSize.SQUARE,
                    count=1,
                    variables=["product_name"],
                    prompt="{product_name}",
                ),
            )
            assert [item.output_role for item in normal_a1.prompt_templates] == [
                OutputRole.MAIN_IMAGE.value,
                OutputRole.DETAIL_IMAGE.value,
            ]
            assert [item.sort_order for item in normal_a1.prompt_templates] == [1, 2]
            assert normal_a1.prompt_templates[1].variables == ["product_name"]

            material_a = service.create_product_material_group(
                self_a1,
                ProductMaterialGroupCreate(name="stage-2a1 AI 素材组 A"),
            )
            material_b = service.create_product_material_group(
                team_b,
                ProductMaterialGroupCreate(name="stage-2a1 AI 素材组 B"),
            )
            self_materials, self_material_total = (
                service.list_product_material_groups(
                    actor=self_a1,
                    page=1,
                    page_size=20,
                    search="stage-2a1 AI 素材组",
                    enabled=None,
                )
            )
            assert self_material_total == 1
            assert [item.material_group_id for item in self_materials] == [
                material_a.material_group_id,
            ]
            all_materials, all_material_total = service.list_product_material_groups(
                actor=all_from_a,
                page=1,
                page_size=20,
                search="stage-2a1 AI 素材组",
                enabled=None,
            )
            assert all_material_total == 2
            assert material_b.material_group_id in {
                item.material_group_id for item in all_materials
            }
            assert (
                service.get_product_material_group(
                    all_from_a,
                    material_b.material_group_id,
                ).material_group_id
                == material_b.material_group_id
            )
            service.attach_asset(
                team_a,
                material_a.material_group_id,
                MaterialGroupAssetAttach(
                    asset_id=same_team_asset_id,
                    role=MaterialRole.PRODUCT_SOURCE,
                ),
            )
            material_a = service.attach_asset(
                team_a,
                material_a.material_group_id,
                MaterialGroupAssetAttach(
                    asset_id=same_team_asset_id,
                    role=MaterialRole.STYLE_REFERENCE,
                ),
            )
            assert len(material_a.asset_links) == 1
            assert material_a.asset_links[0].role == MaterialRole.STYLE_REFERENCE.value
            with pytest.raises(AssetNotFoundError):
                service.attach_asset(
                    all_from_a,
                    material_a.material_group_id,
                    MaterialGroupAssetAttach(
                        asset_id=cross_team_asset_id,
                        role=MaterialRole.PRODUCT_SOURCE,
                    ),
                )
            assert session.scalar(
                select(Asset).where(Asset.asset_id == cross_team_asset_id),
            ) is not None

            material_a = service.replace_template_bindings(
                team_a,
                material_a.material_group_id,
                GenerationMode.NORMAL_GENERATION,
                TemplateBindingReplace(
                    template_group_ids=[
                        normal_a2.template_group_id,
                        normal_a1.template_group_id,
                        normal_a2.template_group_id,
                    ],
                ),
            )
            normal_bindings = [
                item
                for item in material_a.template_bindings
                if item.generation_mode == GenerationMode.NORMAL_GENERATION.value
            ]
            assert [item.template_group_id for item in normal_bindings] == [
                normal_a2.template_group_id,
                normal_a1.template_group_id,
            ]
            assert [item.position for item in normal_bindings] == [0, 1]

            service.update_template_group(
                self_a1,
                normal_a1.template_group_id,
                TemplateGroupUpdate(enabled=False),
            )
            material_a = service.update_product_material_group(
                self_a1,
                material_a.material_group_id,
                ProductMaterialGroupUpdate(
                    enabled=False,
                    normal_generation_enabled=False,
                ),
            )
            assert len(material_a.asset_links) == 1
            assert len(material_a.template_bindings) == 2
            with pytest.raises(TemplateGroupInUseError):
                service.delete_template_group(self_a1, normal_a1.template_group_id)
            assert session.scalar(
                select(TemplateGroup).where(
                    TemplateGroup.template_group_id == normal_a1.template_group_id,
                ),
            ) is not None
            assert session.scalar(
                select(PromptTemplate).where(
                    PromptTemplate.template_group_id == normal_a1.template_group_id,
                ),
            ) is not None

            with pytest.raises(ProductMaterialGroupNotFoundError):
                service.update_product_material_group(
                    all_from_a,
                    material_b.material_group_id,
                    ProductMaterialGroupUpdate(enabled=False),
                )

            service.replace_template_bindings(
                team_a,
                material_a.material_group_id,
                GenerationMode.NORMAL_GENERATION,
                TemplateBindingReplace(
                    template_group_ids=[normal_a2.template_group_id],
                ),
            )
            failing_service = AiWorkbenchService(
                session,
                material_group_repository=FailingProductMaterialGroupRepository(
                    session,
                ),
            )
            with pytest.raises(RuntimeError, match="forced binding transaction failure"):
                failing_service.replace_template_bindings(
                    team_a,
                    material_a.material_group_id,
                    GenerationMode.NORMAL_GENERATION,
                    TemplateBindingReplace(
                        template_group_ids=[normal_a1.template_group_id],
                    ),
                )
            restored_bindings = list(
                session.scalars(
                    select(MaterialGroupTemplateBinding)
                    .where(
                        MaterialGroupTemplateBinding.material_group_id
                        == material_a.material_group_id,
                        MaterialGroupTemplateBinding.generation_mode
                        == GenerationMode.NORMAL_GENERATION.value,
                    )
                    .order_by(MaterialGroupTemplateBinding.position),
                ),
            )
            assert [item.template_group_id for item in restored_bindings] == [
                normal_a2.template_group_id,
            ]

            service.replace_template_bindings(
                team_a,
                material_a.material_group_id,
                GenerationMode.NORMAL_GENERATION,
                TemplateBindingReplace(template_group_ids=[]),
            )
            service.delete_template_group(self_a1, normal_a1.template_group_id)
            assert session.scalar(
                select(PromptTemplate).where(
                    PromptTemplate.template_group_id == normal_a1.template_group_id,
                ),
            ) is None

            service.delete_product_material_group(self_a1, material_a.material_group_id)
            assert session.scalar(
                select(Asset).where(Asset.asset_id == same_team_asset_id),
            ) is not None
            assert session.scalar(
                select(MaterialGroupAsset).where(
                    MaterialGroupAsset.material_group_id == material_a.material_group_id,
                ),
            ) is None
    finally:
        with Session(ai_postgresql_engine) as session:
            session.execute(
                delete(MaterialGroupTemplateBinding).where(
                    MaterialGroupTemplateBinding.material_group_id.in_(
                        select(ProductMaterialGroup.material_group_id).where(
                            ProductMaterialGroup.team_id.in_(team_ids),
                        ),
                    ),
                ),
            )
            session.execute(
                delete(MaterialGroupAsset).where(
                    MaterialGroupAsset.material_group_id.in_(
                        select(ProductMaterialGroup.material_group_id).where(
                            ProductMaterialGroup.team_id.in_(team_ids),
                        ),
                    ),
                ),
            )
            session.execute(
                delete(PromptTemplate).where(
                    PromptTemplate.template_group_id.in_(
                        select(TemplateGroup.template_group_id).where(
                            TemplateGroup.team_id.in_(team_ids),
                        ),
                    ),
                ),
            )
            session.execute(
                delete(ProductMaterialGroup).where(
                    ProductMaterialGroup.team_id.in_(team_ids),
                ),
            )
            session.execute(
                delete(TemplateGroup).where(TemplateGroup.team_id.in_(team_ids)),
            )
            session.execute(delete(Asset).where(Asset.asset_id.in_(asset_ids)))
            session.execute(delete(User).where(User.user_id.in_(user_ids)))
            session.execute(delete(Team).where(Team.team_id.in_(team_ids)))
            session.commit()
