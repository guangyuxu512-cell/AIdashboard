"""Dedicated Feature PG only; temporary local files, no Provider or NAS IO."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
from random import Random
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.database import get_database_engine, get_database_session
from app.main import create_app
from app.modules.access.auth import get_human_principal
from app.modules.access.contracts import ActorContext, HumanPrincipal
from app.modules.access.enums import DataScope
from app.modules.access.models import Team, TeamMembership, TeamModuleAccess
from app.modules.ai_workbench.api import get_ai_asset_service
from app.modules.ai_workbench.asset_service import AiAssetService
from app.modules.ai_workbench.generation_service import GenerationService
from app.modules.ai_workbench.models import AiModel, GenerationItem, GenerationItemAsset, GenerationJob, MaterialGroupAsset, ProductMaterialGroup
from app.modules.ai_workbench.schemas import InstantGenerationSubmit, MaterialGroupAssetAttach, ProductMaterialGroupCreate
from app.modules.ai_workbench.service import AiWorkbenchService
from app.modules.assets.contracts import AssetOwnership
from app.modules.assets.enums import AssetMediaType, AssetSourceType
from app.modules.assets.exceptions import AssetInUseError, AssetNotFoundError
from app.modules.assets.models import Asset
from app.modules.assets.repository import AssetRepository
from app.modules.assets.service import AssetService
from app.modules.assets.storage import LocalAssetStorage
from app.modules.users.models import User

pytestmark = pytest.mark.integration
DATABASE = "control_center_feat_ai_asset_upload_access"


@pytest.fixture()
def context(tmp_path):
    engine = get_database_engine()
    assert engine.url.database == DATABASE, "Refuse non-assigned Feature database"
    with engine.connect() as connection:
        assert connection.scalar(text("select current_database()")) == DATABASE
        assert connection.scalar(text("select version_num from alembic_version")) == "20261017_0047"
    teams, users, model_id = [uuid4(), uuid4()], [uuid4(), uuid4(), uuid4()], uuid4()
    storage = LocalAssetStorage(tmp_path / "assets", 10 * 1024 * 1024)
    session = Session(engine, expire_on_commit=False)
    try:
        session.add_all([Team(team_id=id, name=f"stage-2a1 upload {id}") for id in teams])
        session.add_all([User(user_id=id, display_name=f"stage-2a1 upload {id}", enabled=True) for id in users])
        session.flush()
        for index, user in enumerate(users):
            team = teams[1] if index == 2 else teams[0]
            session.add(TeamMembership(team_id=team, user_id=user, role_code="member", data_scope="team", enabled=True))
        session.add_all([TeamModuleAccess(team_id=id, module_code="ai-workbench") for id in teams])
        session.add(AiModel(model_id=model_id, display_name="stage-2a1 upload model", model_code=f"upload-{model_id}", provider_code="toapis", enabled=True, is_default=False, capabilities=["NORMAL_GENERATION"], max_input_images=6, supported_sizes=["1:1"], supported_resolutions=["1k"]))
        session.commit()
        actor = ActorContext(users[0], "upload actor", teams[0], uuid4(), "member", DataScope.TEAM)
        assets = AssetService(session, storage=storage)
        payload = BytesIO()
        Image.new("RGB", (16, 32), "red").save(payload, format="JPEG")
        def create(owner=0, team=0, source=AssetSourceType.UPLOAD):
            return assets.create(original_filename="stage-2a1.jpg", content_type="image/jpeg", stream=BytesIO(payload.getvalue()), media_type=AssetMediaType.IMAGE, source_type=source, ownership=AssetOwnership(teams[team], users[owner]))
        yield SimpleNamespace(engine=engine, session=session, actor=actor, assets=assets, policy=AiAssetService(session, asset_service=assets), create=create, teams=teams, users=users, model_id=model_id, storage=storage)
    finally:
        session.rollback()
        jobs = select(GenerationJob.generation_job_id).where(GenerationJob.team_id.in_(teams))
        items = select(GenerationItem.generation_item_id).where(GenerationItem.generation_job_id.in_(jobs))
        groups = select(ProductMaterialGroup.material_group_id).where(ProductMaterialGroup.team_id.in_(teams))
        session.execute(delete(GenerationItemAsset).where(GenerationItemAsset.generation_item_id.in_(items)))
        session.execute(delete(GenerationItem).where(GenerationItem.generation_job_id.in_(jobs)))
        session.execute(delete(GenerationJob).where(GenerationJob.team_id.in_(teams)))
        session.execute(delete(MaterialGroupAsset).where(MaterialGroupAsset.material_group_id.in_(groups)))
        session.execute(delete(ProductMaterialGroup).where(ProductMaterialGroup.team_id.in_(teams)))
        session.execute(delete(Asset).where(Asset.team_id.in_(teams)))
        session.execute(delete(AiModel).where(AiModel.model_id == model_id))
        session.execute(delete(TeamModuleAccess).where(TeamModuleAccess.team_id.in_(teams)))
        session.execute(delete(TeamMembership).where(TeamMembership.user_id.in_(users)))
        session.execute(delete(User).where(User.user_id.in_(users)))
        session.execute(delete(Team).where(Team.team_id.in_(teams)))
        session.commit()
        session.close()


def test_owner_draft_reference_scope_and_no_uuid_bootstrap(context):
    c = context
    own, other, foreign = c.create(), c.create(owner=1), c.create(owner=2, team=1)
    content_asset, content = c.policy.get_content(c.actor, own.asset_id)
    assert content_asset.asset_id == own.asset_id
    content.close()
    for asset in (other, foreign):
        with pytest.raises(AssetNotFoundError): c.policy.get_content(c.actor, asset.asset_id)
    service = AiWorkbenchService(c.session, asset_service=c.assets)
    group = service.create_product_material_group(c.actor, ProductMaterialGroupCreate(name="stage-2a1 group"))
    with pytest.raises(AssetNotFoundError):
        service.attach_asset(c.actor, group.material_group_id, MaterialGroupAssetAttach(asset_id=other.asset_id, role="PRODUCT_SOURCE"))
    c.session.rollback()
    generation = GenerationService(c.session, asset_service=c.assets)
    with pytest.raises(AssetNotFoundError):
        generation.submit(c.actor, submission(c, other.asset_id))
    # Establish a legitimate existing AI relation as fixture data. Disabled
    # parent remains readable; foreign-Team malformed links never confer access.
    c.session.add(MaterialGroupAsset(material_group_id=group.material_group_id, asset_id=other.asset_id, role="PRODUCT_SOURCE"))
    c.session.add(MaterialGroupAsset(material_group_id=group.material_group_id, asset_id=foreign.asset_id, role="PRODUCT_SOURCE"))
    group.enabled = False
    c.session.commit()
    c.policy.get_content(c.actor, other.asset_id)[1].close()
    with pytest.raises(AssetNotFoundError): c.policy.get_content(replace(c.actor, data_scope=DataScope.ALL), foreign.asset_id)
    assert foreign.asset_id not in c.policy.references.referenced_asset_ids(c.actor, [foreign.asset_id])
    self_actor = replace(c.actor, data_scope=DataScope.SELF)
    # Current 0037 authority is Team scope, not the retired membership SELF flag.
    c.policy.get_content(self_actor, other.asset_id)[1].close()
    c.session.execute(delete(MaterialGroupAsset).where(MaterialGroupAsset.material_group_id == group.material_group_id))
    c.session.commit()
    with pytest.raises(AssetNotFoundError): c.policy.get_content(c.actor, other.asset_id)
    c.session.add(TeamModuleAccess(team_id=c.actor.team_id, module_code="asset"))
    c.session.commit()
    service.attach_asset(c.actor, group.material_group_id, MaterialGroupAssetAttach(asset_id=other.asset_id, role="PRODUCT_SOURCE"))


def submission(c, asset_id):
    return InstantGenerationSubmit(work_mode="INSTANT", submission_key=str(uuid4()), model_id=c.model_id, mode="NORMAL_GENERATION", product_asset_ids=[asset_id], prompt="stage-2a1 no provider", output_format="SINGLE", size="1:1", count=1)


def test_job_input_output_history_and_retry_cannot_cross_team(context):
    c = context
    own, generated, foreign = c.create(), c.create(owner=1, source=AssetSourceType.AI_GENERATED), c.create(owner=2, team=1)
    generation = GenerationService(c.session, asset_service=c.assets)
    job = generation.submit(c.actor, submission(c, own.asset_id))
    item = job.items[0]
    item.output_asset_id, item.status, job.status = generated.asset_id, "SUCCESS", "SUCCESS"
    c.session.commit()
    assert generated.asset_id in c.policy.references.referenced_asset_ids(c.actor, [own.asset_id, generated.asset_id])
    c.policy.get_content(c.actor, generated.asset_id)[1].close()
    with pytest.raises(AssetNotFoundError): c.policy.cleanup(c.actor, generated.asset_id)
    with pytest.raises(AssetInUseError): c.policy.cleanup(c.actor, own.asset_id)
    item.status, job.status, item.output_asset_id = "FAILED", "FAILED", None
    item.input_assets[0].asset_id = foreign.asset_id
    c.session.commit()
    from app.modules.ai_workbench.schemas import GenerationRetryRequest
    with pytest.raises(AssetNotFoundError):
        generation.retry_failed_items(c.actor, job.generation_job_id, GenerationRetryRequest(items=[{"item_id": item.generation_item_id, "expected_attempt_count": 1}]))
    c.session.rollback()
    assert c.session.get(GenerationItem, item.generation_item_id).status == "FAILED"


def test_ai_only_real_asgi_large_jpeg_upload_read_cleanup_and_revocation(context):
    c = context
    image = Image.frombytes("RGB", (1600, 1200), Random(73).randbytes(1600 * 1200 * 3))
    payload = BytesIO()
    image.save(payload, format="JPEG", quality=95)
    data = payload.getvalue()
    assert 1024 * 1024 < len(data) < 10 * 1024 * 1024
    app = create_app()
    app.dependency_overrides[get_human_principal] = lambda: HumanPrincipal(c.actor.user_id, "stage-2a1 principal")
    app.dependency_overrides[get_database_session] = lambda: c.session
    app.dependency_overrides[get_ai_asset_service] = lambda: c.policy
    async def exercise():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver") as client:
            assert (await client.get("/api/v1/assets")).status_code == 403
            upload = await client.post("/api/v1/ai-workbench/assets", files={"file": ("stage-2a1-large.jpg", data, "image/jpeg")})
            assert upload.status_code == 201
            asset_id = upload.json()["asset_id"]
            assert upload.json()["size_bytes"] == len(data)
            content = await client.get(f"/api/v1/ai-workbench/assets/{asset_id}/content")
            assert content.status_code == 200 and content.content == data
            assert (await client.get(f"/api/v1/ai-workbench/assets/{asset_id}/thumbnail")).status_code == 200
            group = await client.post(
                "/api/v1/ai-workbench/product-material-groups",
                json={"name": "stage-2a1 uploaded JPEG"},
            )
            assert group.status_code == 201
            group_id = group.json()["material_group_id"]
            relation_path = f"/api/v1/ai-workbench/product-material-groups/{group_id}/assets"
            attached = await client.post(
                relation_path, json={"asset_id": asset_id, "role": "PRODUCT_SOURCE"}
            )
            assert attached.status_code == 200
            assert attached.json()["assets"][0]["asset"]["asset_id"] == asset_id
            in_use = await client.delete(f"/api/v1/ai-workbench/assets/{asset_id}")
            assert in_use.status_code == 409 and in_use.json()["code"] == "ASSET_IN_USE"
            assert (await client.delete(f"{relation_path}/{asset_id}")).status_code == 204
            assert (await client.delete(f"/api/v1/ai-workbench/assets/{asset_id}")).status_code == 204
            assert (await client.get(f"/api/v1/ai-workbench/assets/{asset_id}/content")).status_code == 404
            c.session.execute(delete(TeamModuleAccess).where(TeamModuleAccess.team_id == c.actor.team_id))
            c.session.commit()
            denied = await client.post("/api/v1/ai-workbench/assets", files={"file": ("denied.jpg", data, "image/jpeg")})
            assert denied.status_code == 403 and denied.json()["code"] == "MODULE_ACCESS_DENIED"
    asyncio.run(exercise())


@pytest.mark.parametrize("winner", ["attach", "cleanup"])
def test_attach_cleanup_serialize_on_real_asset_row_lock(context, winner):
    c = context
    asset = c.create()
    group = AiWorkbenchService(c.session, asset_service=c.assets).create_product_material_group(c.actor, ProductMaterialGroupCreate(name="stage-2a1 lock"))
    asset_id, group_id, actor = asset.asset_id, group.material_group_id, c.actor
    c.session.rollback()
    locked, release, contender_started = Event(), Event(), Event()
    contender_pid = []

    class HoldingRepository(AssetRepository):
        def get_for_actor_for_update(self, **kwargs):
            result = super().get_for_actor_for_update(**kwargs)
            if winner == "cleanup":
                locked.set()
                assert release.wait(10), "Test did not release cleanup row lock"
            return result

    class HoldingAssetService(AssetService):
        def list_accessible_by_ids_for_update(self, *args):
            result = super().list_accessible_by_ids_for_update(*args)
            if winner == "attach":
                locked.set()
                assert release.wait(10), "Test did not release attach row lock"
            return result

    def operation(name, hold=False):
        with Session(c.engine, expire_on_commit=False) as session:
            assets = (HoldingAssetService if hold else AssetService)(session, storage=c.storage, repository=HoldingRepository(session) if hold else AssetRepository(session))
            if not hold:
                contender_pid.append(session.scalar(text("select pg_backend_pid()")))
                contender_started.set()
            try:
                if name == "attach":
                    AiWorkbenchService(session, asset_service=assets).attach_asset(actor, group_id, MaterialGroupAssetAttach(asset_id=asset_id, role="PRODUCT_SOURCE"))
                else:
                    AiAssetService(session, asset_service=assets).cleanup(actor, asset_id)
                return "ok"
            except (AssetNotFoundError, AssetInUseError) as error:
                session.rollback()
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(operation, winner, True)
        assert locked.wait(10)
        second = pool.submit(operation, "cleanup" if winner == "attach" else "attach")
        try:
            assert contender_started.wait(10)
            deadline = monotonic() + 5
            while monotonic() < deadline:
                with c.engine.connect() as connection:
                    blocked = connection.scalar(text("select cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": contender_pid[0]})
                if blocked: break
                sleep(0.02)
            assert blocked, "Contender did not wait on the real PostgreSQL row lock"
        finally:
            release.set()
        assert first.result(timeout=10) == "ok"
        assert second.result(timeout=10) == ("ASSET_IN_USE" if winner == "attach" else "ASSET_NOT_FOUND")
    present = c.session.scalar(select(Asset.asset_id).where(Asset.asset_id == asset_id))
    link = c.session.scalar(select(MaterialGroupAsset.asset_id).where(MaterialGroupAsset.material_group_id == group_id))
    assert (present is not None, link is not None) == ((True, True) if winner == "attach" else (False, False))
