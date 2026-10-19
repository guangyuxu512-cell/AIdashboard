"""Exact assigned Feature DB; real authorization/SQL, temporary local images."""
import asyncio
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.core.database import get_database_engine, get_database_session
from app.main import create_app
from app.modules.access.auth import get_human_principal
from app.modules.access.contracts import HumanPrincipal
from app.modules.access.models import Team, TeamMembership, TeamModuleAccess
from app.modules.ai_workbench.api import get_ai_asset_service, get_ai_workbench_service
from app.modules.ai_workbench.asset_service import AiAssetService
from app.modules.ai_workbench.models import MaterialGroupAsset, ProductMaterialGroup, TemplateGroup
from app.modules.ai_workbench.service import AiWorkbenchService
from app.modules.assets.models import Asset
from app.modules.assets.service import AssetService
from app.modules.assets.storage import LocalAssetStorage
from app.modules.users.models import User

pytestmark = pytest.mark.integration
DATABASE = "control_center_feat_super_account_team_context"


@pytest.fixture()
def context(tmp_path):
    engine = get_database_engine()
    assert engine.url.database == DATABASE, "Refuse any non-assigned database"
    with engine.connect() as connection:
        assert connection.scalar(text("select current_database()")) == DATABASE
        assert connection.scalar(text("select version_num from alembic_version")) == "20261017_0047"
        privileges = connection.execute(text(
            "select rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
            "from pg_roles where rolname = current_user"
        )).one()
        assert not any(privileges)
    teams, users = [uuid4(), uuid4()], [uuid4(), uuid4(), uuid4()]
    models = (Team, User, TeamMembership, TeamModuleAccess, Asset, ProductMaterialGroup, TemplateGroup, MaterialGroupAsset)
    session = Session(engine, expire_on_commit=False)
    before = {model: session.scalar(select(func.count()).select_from(model)) for model in models}
    try:
        session.add_all([
            Team(team_id=teams[0], name=f"stage-2a1 默认团队 {teams[0]}", enabled=True),
            Team(team_id=teams[1], name=f"stage-2a1 shopee {teams[1]}", enabled=True),
            User(user_id=users[0], display_name="stage-2a1 super", enabled=True, is_super_account=True),
            User(user_id=users[1], display_name="stage-2a1 default member", enabled=True),
            User(user_id=users[2], display_name="stage-2a1 shopee member", enabled=True),
        ])
        session.flush()
        for index, team_id in enumerate(teams):
            session.add(TeamMembership(team_id=team_id, user_id=users[index + 1], role_code="member", data_scope="team", enabled=True))
            session.add(TeamModuleAccess(team_id=team_id, module_code="ai-workbench"))
        session.commit()
        assets = AssetService(session, storage=LocalAssetStorage(tmp_path / "assets", 10 * 1024 * 1024))
        app = create_app()
        principal = {"user_id": users[0]}
        app.dependency_overrides[get_human_principal] = lambda: HumanPrincipal(principal["user_id"], "stage-2a1 principal")
        app.dependency_overrides[get_database_session] = lambda: session
        app.dependency_overrides[get_ai_asset_service] = lambda: AiAssetService(session, asset_service=assets)
        app.dependency_overrides[get_ai_workbench_service] = lambda: AiWorkbenchService(session, asset_service=assets)
        groups = [
            ProductMaterialGroup(material_group_id=uuid4(), team_id=team_id, created_by_user_id=users[0], name=name)
            for team_id, name in zip(teams, ("stage-2a1 默认产品", "stage-2a1 shopee 70收纳柜"), strict=True)
        ]
        templates = [
            TemplateGroup(template_group_id=uuid4(), team_id=team_id, created_by_user_id=users[0], name=f"stage-2a1 template {index}", mode="NORMAL_GENERATION")
            for index, team_id in enumerate(teams)
        ]
        session.add_all([*groups, *templates])
        session.commit()
        yield SimpleNamespace(app=app, session=session, teams=teams, users=users, principal=principal, groups=groups, templates=templates)
    finally:
        session.rollback()
        group_ids = select(ProductMaterialGroup.material_group_id).where(ProductMaterialGroup.team_id.in_(teams))
        session.execute(delete(MaterialGroupAsset).where(MaterialGroupAsset.material_group_id.in_(group_ids)))
        for model in (ProductMaterialGroup, TemplateGroup, Asset, TeamModuleAccess, TeamMembership):
            session.execute(delete(model).where(model.team_id.in_(teams)))
        session.execute(delete(User).where(User.user_id.in_(users)))
        session.execute(delete(Team).where(Team.team_id.in_(teams)))
        session.commit()
        assert {model: session.scalar(select(func.count()).select_from(model)) for model in models} == before
        session.close()


def team_headers(team_id):
    return {"X-Team-ID": str(team_id)} if team_id is not None else {}


@pytest.mark.parametrize("selected", [None, 0, 1])
def test_super_global_and_selected_team_match_lists_counts_search_and_details(context, selected):
    c = context
    headers = team_headers(c.teams[selected] if selected is not None else None)
    visible = {group.material_group_id for group in c.groups} if selected is None else {c.groups[selected].material_group_id}

    async def exercise():
        async with AsyncClient(transport=ASGITransport(app=c.app), base_url="https://testserver") as client:
            response = await client.get("/api/v1/ai-workbench/product-material-groups", headers=headers)
            assert response.status_code == 200
            assert response.json()["total"] == len(visible)
            assert {UUID(row["material_group_id"]) for row in response.json()["items"]} == visible
            paged = await client.get("/api/v1/ai-workbench/product-material-groups?page_size=1", headers=headers)
            assert paged.json()["total"] == len(visible) and len(paged.json()["items"]) == 1
            search = await client.get("/api/v1/ai-workbench/product-material-groups?search=shopee", headers=headers)
            assert search.json()["total"] == (0 if selected == 0 else 1)
            for group in c.groups:
                detail = await client.get(f"/api/v1/ai-workbench/product-material-groups/{group.material_group_id}", headers=headers)
                assert detail.status_code == (200 if group.material_group_id in visible else 404)
            templates = await client.get("/api/v1/ai-workbench/template-groups", headers=headers)
            assert templates.status_code == 200 and templates.json()["total"] == len(visible)

    asyncio.run(exercise())


def test_upload_and_material_attachment_share_the_selected_team(context):
    c = context
    output = BytesIO()
    Image.new("RGBA", (32, 24), (0, 100, 200, 128)).save(output, format="PNG")
    data = output.getvalue()

    async def exercise():
        async with AsyncClient(transport=ASGITransport(app=c.app), base_url="https://testserver") as client:
            global_upload = await client.post("/api/v1/ai-workbench/assets", files={"file": ("stage-2a1.png", data, "image/png")})
            assert global_upload.status_code == 409 and global_upload.json()["code"] == "TEAM_CONTEXT_REQUIRED"
            for index, team_id in enumerate(c.teams):
                headers = team_headers(team_id)
                uploaded = await client.post("/api/v1/ai-workbench/assets", headers=headers, files={"file": ("stage-2a1.png", data, "image/png")})
                assert uploaded.status_code == 201
                asset_id = uploaded.json()["asset_id"]
                assert c.session.get(Asset, UUID(asset_id)).team_id == team_id
                foreign = await client.post(f"/api/v1/ai-workbench/product-material-groups/{c.groups[1-index].material_group_id}/assets", headers=headers, json={"asset_id": asset_id, "role": "PRODUCT_SOURCE"})
                assert foreign.status_code == 404 and foreign.json()["code"] == "PRODUCT_MATERIAL_GROUP_NOT_FOUND"
                attached = await client.post(f"/api/v1/ai-workbench/product-material-groups/{c.groups[index].material_group_id}/assets", headers=headers, json={"asset_id": asset_id, "role": "PRODUCT_SOURCE"})
                assert attached.status_code == 200
                assert attached.json()["assets"][0]["asset"]["asset_id"] == asset_id
                assert (await client.get(f"/api/v1/ai-workbench/assets/{asset_id}/content", headers=team_headers(c.teams[1-index]))).status_code == 404
                read = await client.get(f"/api/v1/ai-workbench/assets/{asset_id}/content", headers=headers)
                assert read.status_code == 200 and read.content == data

    asyncio.run(exercise())


def test_ordinary_member_never_gains_global_or_another_teams_data(context):
    c = context
    c.principal["user_id"] = c.users[1]

    async def exercise():
        async with AsyncClient(transport=ASGITransport(app=c.app), base_url="https://testserver") as client:
            own = await client.get("/api/v1/ai-workbench/product-material-groups")
            assert own.status_code == 200 and own.json()["total"] == 1
            assert own.json()["items"][0]["material_group_id"] == str(c.groups[0].material_group_id)
            forged = await client.get("/api/v1/ai-workbench/product-material-groups", headers=team_headers(c.teams[1]))
            assert forged.status_code == 403 and forged.json()["code"] == "TEAM_ACCESS_DENIED"
            foreign = await client.get(f"/api/v1/ai-workbench/product-material-groups/{c.groups[1].material_group_id}")
            assert foreign.status_code == 404

    asyncio.run(exercise())
