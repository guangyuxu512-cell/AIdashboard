from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.module_access import ModuleCode
from app.modules.ai_workbench.asset_service import AiAssetService
from app.modules.assets.exceptions import AssetInUseError, AssetNotFoundError
from app.modules.assets.models import Asset
from tests.support import FakeSession


def setup_policy():
    actor = ActorContext(uuid4(), "AI only", uuid4(), uuid4(), "member", DataScope.TEAM)
    assets = Mock()
    references = Mock()
    references.referenced_asset_ids.return_value = set()
    modules = Mock()
    modules.list_for_actor.return_value = [ModuleCode.AI_WORKBENCH]
    session = FakeSession()
    service = AiAssetService(session, asset_service=assets, references=references, module_access=modules)
    asset = Asset(asset_id=uuid4(), team_id=actor.team_id, created_by_user_id=actor.user_id,
                  source_type="upload", media_type="image")
    return actor, service, asset, assets, references, modules, session


def test_ai_only_owner_upload_draft_does_not_need_asset_module_or_fake_ai_reference():
    actor, service, asset, _, references, modules, _ = setup_policy()
    service.require_eligible(actor, [asset])
    references.referenced_asset_ids.assert_not_called()
    modules.list_for_actor.assert_not_called()


@pytest.mark.parametrize("source", ["upload", "ai_generated", "imported"])
def test_ai_only_cannot_bootstrap_unrelated_same_team_asset_into_ai(source):
    actor, service, asset, _, _, _, _ = setup_policy()
    asset.created_by_user_id = uuid4()
    asset.source_type = source
    with pytest.raises(AssetNotFoundError):
        service.require_eligible(actor, [asset])


def test_real_visible_ai_reference_or_existing_asset_grant_retains_input_use():
    actor, service, asset, _, references, modules, _ = setup_policy()
    asset.created_by_user_id = uuid4()
    references.referenced_asset_ids.return_value = {asset.asset_id}
    service.require_eligible(actor, [asset])
    references.referenced_asset_ids.return_value = set()
    modules.list_for_actor.return_value = [ModuleCode.AI_WORKBENCH, ModuleCode.ASSET]
    service.require_eligible(actor, [asset])


def test_image_kind_is_required_even_with_general_asset_permission():
    actor, service, asset, _, _, modules, _ = setup_policy()
    asset.media_type = "video"
    modules.list_for_actor.return_value = [ModuleCode.ASSET]
    with pytest.raises(AssetNotFoundError):
        service.require_eligible(actor, [asset])


@pytest.mark.parametrize("change", ["owner", "team", "generated", "null_creator"])
def test_ai_cleanup_cannot_delete_others_foreign_or_generated_assets(change):
    actor, service, asset, assets, _, _, session = setup_policy()
    if change == "owner": asset.created_by_user_id = uuid4()
    if change == "team": asset.team_id = uuid4()
    if change == "generated": asset.source_type = "ai_generated"
    if change == "null_creator": asset.created_by_user_id = None
    assets.repository.get_for_actor_for_update.return_value = asset
    with pytest.raises(AssetNotFoundError):
        service.cleanup(actor, asset.asset_id)
    assets.delete.assert_not_called()
    assert session.rollbacks == 1


def test_ai_cleanup_holds_original_asset_lock_and_keeps_all_reference_protection():
    actor, service, asset, assets, _, _, _ = setup_policy()
    assets.repository.get_for_actor_for_update.return_value = asset
    assets.delete.side_effect = AssetInUseError()
    with pytest.raises(AssetInUseError):
        service.cleanup(actor, asset.asset_id)
    assets.repository.get_for_actor_for_update.assert_called_once_with(actor=actor, asset_id=asset.asset_id)
    assets.delete.assert_called_once_with(actor, asset.asset_id)
