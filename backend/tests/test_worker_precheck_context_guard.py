from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.sessions.application_auth import ApplicationPrincipal, ClientGrant
from app.modules.workers.precheck_contract import PrecheckSubmission
from app.modules.workers.precheck_service import PrecheckUnavailable, WorkerPrecheckService


def _grant(**extra):
    device = uuid4()
    return ClientGrant(client_id='product-library', token_sha256='a' * 64,
        authorized_by_user_id=uuid4(), enabled=True, worker_precheck_enabled=True,
        device_ids=(device,), all_mapped_shops=(device,), **extra)


def _submission(product='one', revision=3):
    return PrecheckSubmission.model_validate({'kind': 'douyin.category_schema',
        'context': {'product_id': product, 'revision': revision, 'attempt': 1},
        'input': {'category_id': '123', 'title': 'synthetic'}})


def test_scope_is_optional_and_only_accepts_a_strict_product_revision():
    assert _grant().precheck_context is None
    grant = _grant(precheck_context={'product_id': 'one', 'revision': 3})
    WorkerPrecheckService._require_allowed_context(grant, _submission())
    for value in (_submission(product='other'), _submission(revision=4)):
        with pytest.raises(PrecheckUnavailable):
            WorkerPrecheckService._require_allowed_context(grant, value)
    with pytest.raises(ValidationError):
        _grant(precheck_context={'product_id': 'one', 'revision': '3'})


def test_blocked_product_fails_before_query_or_task_creation():
    grant = _grant(precheck_context={'product_id': 'one', 'revision': 3})
    principal = ApplicationPrincipal(grant, 'synthetic')
    auth = Mock()
    auth.authenticate.return_value = principal
    session = Mock()
    session.get.return_value = SimpleNamespace(enabled=True, is_super_account=True)
    with pytest.raises(PrecheckUnavailable):
        WorkerPrecheckService(session, auth).submit(principal, _submission('other'))
    session.execute.assert_not_called()
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_context_requires_precheck_opt_in():
    data = _grant(precheck_context={'product_id': 'one', 'revision': 3}).model_dump()
    data.update(worker_precheck_enabled=False, device_ids=(), all_mapped_shops=(), shop_ids=(uuid4(),))
    with pytest.raises(ValidationError):
        ClientGrant.model_validate(data)
