from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete, inspect, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.models import Team
from app.modules.assets.contracts import AssetOwnership
from app.modules.assets.enums import AssetMediaType, AssetSourceType
from app.modules.assets.exceptions import AssetNotFoundError
from app.modules.assets.models import Asset
from app.modules.assets.service import AssetService
from app.modules.assets.storage import LocalAssetStorage
from app.modules.users.models import User


pytestmark = pytest.mark.integration


def _actor(
    *,
    user_id: UUID,
    team_id: UUID,
    scope: DataScope,
    is_super_account: bool = False,
) -> ActorContext:
    return ActorContext(
        user_id=user_id,
        user_display_name=f"Asset Scope {scope.value}",
        team_id=team_id,
        membership_id=uuid4(),
        role_code="member",
        data_scope=scope,
        is_super_account=is_super_account,
    )


def _internal_create(
    service: AssetService,
    *,
    filename: str,
    ownership: AssetOwnership,
) -> Asset:
    return service.create(
        original_filename=filename,
        content_type="image/png",
        stream=BytesIO(b"\x89PNG\r\n\x1a\n" + filename.encode()),
        media_type=AssetMediaType.IMAGE,
        source_type=AssetSourceType.IMPORTED,
        ownership=ownership,
    )


def test_postgresql_asset_scope_ownership_and_sql_isolation(
    postgresql_engine: Engine,
    tmp_path: Path,
) -> None:
    inspector = inspect(postgresql_engine)
    asset_columns = {
        column["name"]: column for column in inspector.get_columns("assets")
    }
    assert asset_columns["team_id"]["nullable"] is False
    assert asset_columns["created_by_user_id"]["nullable"] is True
    asset_foreign_keys = {
        key["name"]: key for key in inspector.get_foreign_keys("assets")
    }
    assert asset_foreign_keys["fk_assets_team_id_teams"]["referred_table"] == ("teams")
    assert (
        asset_foreign_keys["fk_assets_created_by_user_id_users"]["referred_table"]
        == "users"
    )
    assert {
        "ix_assets_team_created_asset",
        "ix_assets_team_creator_created_asset",
    } <= {index["name"] for index in inspector.get_indexes("assets")}

    team_a_id, team_b_id = uuid4(), uuid4()
    user_a1_id, user_a2_id, user_b_id, all_user_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    team_ids = {team_a_id, team_b_id}
    user_ids = {user_a1_id, user_a2_id, user_b_id, all_user_id}
    asset_ids: set[UUID] = set()
    storage = LocalAssetStorage(tmp_path / "assets", 1024 * 1024)
    settings = Settings(asset_storage_dir=tmp_path / "assets")

    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    Team(team_id=team_a_id, name="素材范围团队A", enabled=True),
                    Team(team_id=team_b_id, name="素材范围团队B", enabled=True),
                    User(
                        user_id=user_a1_id,
                        display_name="素材用户A1",
                        enabled=True,
                    ),
                    User(
                        user_id=user_a2_id,
                        display_name="素材用户A2",
                        enabled=True,
                    ),
                    User(
                        user_id=user_b_id,
                        display_name="素材用户B",
                        enabled=True,
                    ),
                    User(
                        user_id=all_user_id,
                        display_name="素材全局用户",
                        enabled=True,
                        is_super_account=True,
                    ),
                ],
            )
            session.commit()

            member_actor = _actor(
                user_id=user_a1_id,
                team_id=team_a_id,
                scope=DataScope.TEAM,
            )
            super_actor = _actor(
                user_id=all_user_id,
                team_id=team_a_id,
                scope=DataScope.ALL,
                is_super_account=True,
            )
            service = AssetService(
                session,
                storage=storage,
                settings=settings,
            )

            owned_by_a1 = service.upload(
                actor=member_actor,
                original_filename="team-a-user-a1.png",
                content_type="image/png",
                stream=BytesIO(b"\x89PNG\r\n\x1a\na1"),
            )
            owned_by_a2 = _internal_create(
                service,
                filename="team-a-user-a2.png",
                ownership=AssetOwnership(team_a_id, user_a2_id),
            )
            legacy_team_a = _internal_create(
                service,
                filename="team-a-legacy.png",
                ownership=AssetOwnership(team_a_id, None),
            )
            team_b_asset = _internal_create(
                service,
                filename="cross-team-secret.png",
                ownership=AssetOwnership(team_b_id, user_b_id),
            )
            created_by_super = service.upload(
                actor=super_actor,
                original_filename="all-user-active-team.png",
                content_type="image/png",
                stream=BytesIO(b"\x89PNG\r\n\x1a\nall"),
            )
            asset_ids.update(
                {
                    owned_by_a1.asset_id,
                    owned_by_a2.asset_id,
                    legacy_team_a.asset_id,
                    team_b_asset.asset_id,
                    created_by_super.asset_id,
                },
            )

            assert owned_by_a1.team_id == team_a_id
            assert owned_by_a1.created_by_user_id == user_a1_id
            assert created_by_super.team_id == team_a_id
            assert created_by_super.created_by_user_id == all_user_id

            member_items, member_total = service.list(
                actor=member_actor,
                page=1,
                page_size=20,
                search=None,
            )
            assert member_total == 4
            assert {item.asset_id for item in member_items} == {
                owned_by_a1.asset_id,
                owned_by_a2.asset_id,
                legacy_team_a.asset_id,
                created_by_super.asset_id,
            }

            all_items, all_total = service.list(
                actor=super_actor,
                page=1,
                page_size=20,
                search=None,
            )
            assert all_total == 5
            assert {item.asset_id for item in all_items} == asset_ids

            searched, searched_total = service.list(
                actor=member_actor,
                page=1,
                page_size=20,
                search="cross-team",
            )
            assert searched == []
            assert searched_total == 0

            accessible = service.list_accessible_by_ids(
                member_actor,
                [owned_by_a1.asset_id, team_b_asset.asset_id],
            )
            assert [asset.asset_id for asset in accessible] == [owned_by_a1.asset_id]

            with pytest.raises(AssetNotFoundError):
                service.get_for_actor(member_actor, team_b_asset.asset_id)
            with pytest.raises(AssetNotFoundError):
                service.get_content(member_actor, team_b_asset.asset_id)
            with pytest.raises(AssetNotFoundError):
                service.delete(member_actor, team_b_asset.asset_id)
            assert (
                session.scalar(
                    select(Asset).where(Asset.asset_id == team_b_asset.asset_id),
                )
                is not None
            )

            legacy, content = service.get_content(member_actor, legacy_team_a.asset_id)
            with content:
                assert content.read().startswith(b"\x89PNG")
            assert legacy.created_by_user_id is None
    finally:
        with Session(postgresql_engine) as session:
            session.execute(delete(Asset).where(Asset.asset_id.in_(asset_ids)))
            session.execute(delete(User).where(User.user_id.in_(user_ids)))
            session.execute(delete(Team).where(Team.team_id.in_(team_ids)))
            session.commit()
