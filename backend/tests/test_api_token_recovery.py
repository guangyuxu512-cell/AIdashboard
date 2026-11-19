from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.api_tokens.exceptions import ApiTokenNotFoundError, ApiTokenNotRecoverableError, ApiTokenRecoveryUnavailableError
from app.modules.api_tokens.models import ApiToken, ApiTokenEvent
from app.modules.api_tokens.service import ApiTokenService
from app.modules.audit.models import AuditLog


class Session:
    def __init__(self):
        self.rows = []
        self.commits = 0

    def add(self, obj):
        self.rows.append(obj)

    def flush(self):
        pass

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        pass

    def get(self, kind, identifier):
        return next((item for item in self.rows if isinstance(item, kind) and item.token_id == identifier), None)


def issue(service, actor, **kwargs):
    return service.issue(actor=actor, request_id="test-request", name="test", permissions=["read"], team_ids=None,
                         enabled=True, expires_at=None, catalog=[{"id": "read", "team_scoped": False}], **kwargs)


def test_new_token_can_be_viewed_with_configured_key_without_storing_plaintext():
    session = Session()
    service = ApiTokenService(session)
    actor = SimpleNamespace(user_id=uuid4())
    key = "test-only-recovery-key-0123456789abcdef"
    issued = issue(service, actor, recoverable=True, recovery_key=key)
    assert issued.raw_token != issued.record.token_hash
    assert issued.raw_token not in str(issued.record.__dict__)
    assert len([row for row in session.rows if isinstance(row, ApiTokenEvent)]) == 1
    for _ in range(2):
        assert service.reveal(issued.record.token_id, actor=actor, request_id="test-request", recovery_key=key) == issued.raw_token
    audits = [row for row in session.rows if isinstance(row, AuditLog)]
    assert len(audits) == 2 and all(row.action == "api_token.reveal" for row in audits)
    assert all(issued.raw_token not in str(row.__dict__) for row in audits)


def test_old_tokens_wrong_key_and_revoked_tokens_are_never_replaced_or_disclosed():
    session = Session()
    service = ApiTokenService(session)
    actor = SimpleNamespace(user_id=uuid4())
    key = "test-only-recovery-key-0123456789abcdef"
    old = issue(service, actor)
    before = old.record.token_hash
    with pytest.raises(ApiTokenNotRecoverableError):
        service.reveal(old.record.token_id, actor=actor, request_id="test-request", recovery_key=key)
    assert old.record.token_hash == before
    new = issue(service, actor, recoverable=True, recovery_key=key)
    with pytest.raises(ApiTokenRecoveryUnavailableError):
        service.reveal(new.record.token_id, actor=actor, request_id="test-request", recovery_key=None)
    with pytest.raises(ApiTokenNotRecoverableError):
        service.reveal(new.record.token_id, actor=actor, request_id="test-request", recovery_key="wrong-test-key-0123456789abcdef01234567")
    new.record.revoked_at = object()
    with pytest.raises(ApiTokenNotFoundError):
        service.reveal(new.record.token_id, actor=actor, request_id="test-request", recovery_key=key)
    assert not any(isinstance(row, AuditLog) for row in session.rows)


def test_recoverable_issuance_fails_closed_without_key_but_legacy_issuance_works():
    session = Session()
    service = ApiTokenService(session)
    actor = SimpleNamespace(user_id=uuid4())
    with pytest.raises(ApiTokenRecoveryUnavailableError):
        issue(service, actor, recoverable=True)
    assert not session.rows
    assert issue(service, actor).raw_token.startswith("ccai_")
