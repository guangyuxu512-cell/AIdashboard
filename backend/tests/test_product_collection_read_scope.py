"""Collection reads share DataScopePolicy; global browsing never grants writes."""

from dataclasses import replace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.exceptions import ModuleAccessDeniedError, TeamContextRequiredError
from app.modules.product_collection.human_repository import ProductCollectionHumanRepository
from app.modules.product_collection.human_service import ProductCollectionHumanService


def _actor(*, super_account=True, team_id=None):
    return ActorContext(uuid4(), "stage-2a1-read-scope", team_id, None,
                        "member", DataScope.ALL, is_super_account=super_account)


@pytest.mark.parametrize("super_account,selected_team", [(True, False), (True, True), (False, True)])
def test_collection_sql_scope_before_pagination(super_account, selected_team):
    actor = _actor(super_account=super_account, team_id=uuid4() if selected_team else None)
    statement = ProductCollectionHumanRepository.visible_requests(actor)
    compiled = statement.compile(dialect=postgresql.dialect())
    assert ("product_collection_requests.team_id =" in str(compiled)) == selected_team
    assert list(compiled.params.values()) == ([actor.team_id] if selected_team else [])


def test_global_super_can_list_and_read_collection_requests_without_a_write_team():
    service = ProductCollectionHumanService(Mock())
    service.repository = Mock(spec=ProductCollectionHumanRepository)
    service.repository.list_requests.return_value = ([], 0)
    service.repository.request_for_actor.return_value = object()
    service._request_read = Mock(return_value="synthetic-detail")
    actor, request_id = _actor(), uuid4()
    assert service.list_requests(actor, offset=0, limit=20) == ([], 0)
    assert service.get_request(actor, request_id) == "synthetic-detail"
    service.repository.request_for_actor.assert_called_once_with(actor=actor, request_id=request_id)


def test_module_guard_and_missing_member_team_still_fail_closed():
    service = ProductCollectionHumanService(Mock())
    service.module_access.repository = Mock()
    service.module_access.repository.has_module_access.return_value = False
    actor = _actor(super_account=False, team_id=uuid4())
    for operation in (lambda: service.list_requests(actor, offset=0, limit=20),
                      lambda: service.get_request(actor, uuid4())):
        with pytest.raises(ModuleAccessDeniedError):
            operation()
    with pytest.raises(TeamContextRequiredError):
        service.list_requests(replace(actor, team_id=None), offset=0, limit=20)


@pytest.mark.parametrize("action", ["create", "cancel", "retry", "recapture"])
def test_global_super_writes_require_explicit_team_before_persistence(action):
    session = Mock()
    service = ProductCollectionHumanService(session)
    actor, identifier = _actor(), uuid4()
    actions = {
        "create": lambda: service.create_request(actor, Mock()),
        "cancel": lambda: service.cancel_request(actor, identifier),
        "retry": lambda: service.retry_item(actor, identifier, max_delivery_attempts=3, max_capture_attempts=3),
        "recapture": lambda: service.recapture_item(actor, identifier, gateway_id="synthetic-gateway"),
    }
    with pytest.raises(TeamContextRequiredError):
        actions[action]()
    assert session.mock_calls == []
