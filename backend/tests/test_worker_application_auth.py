import hashlib
import json
from uuid import uuid4

import pytest

from app.modules.sessions.application_auth import (
    ApplicationAuthenticationError,
    ApplicationAuthenticator,
    ApplicationSessionUnavailableError,
)


def test_application_worker_grants_are_checked_and_reread(tmp_path):
    token = 'synthetic_test_application_token_0123456789'
    path = tmp_path / 'grants.json'
    client = {
        'client_id': 'pdc-test', 'token_sha256': hashlib.sha256(token.encode()).hexdigest(),
        'authorized_by_user_id': str(uuid4()), 'enabled': True,
        'worker_precheck_enabled': True, 'device_ids': [str(uuid4())],
    }
    path.write_text(json.dumps({'version': 1, 'clients': [client]}), encoding='utf-8')
    auth = ApplicationAuthenticator(enabled=True, path=path)
    assert auth.authenticate('pdc-test', token).grant.client_id == 'pdc-test'
    with pytest.raises(ApplicationAuthenticationError):
        auth.authenticate('pdc-test', 'another_synthetic_token_0123456789')
    client['enabled'] = False
    path.write_text(json.dumps({'version': 1, 'clients': [client]}), encoding='utf-8')
    with pytest.raises(ApplicationAuthenticationError):
        auth.authenticate('pdc-test', token)
    with pytest.raises(ApplicationSessionUnavailableError):
        ApplicationAuthenticator(enabled=False, path=path).authenticate('pdc-test', token)


def test_application_auth_rejects_duplicate_credentials(tmp_path):
    token = 'synthetic_test_application_token_0123456789'
    device_id = str(uuid4())
    client = {'client_id': 'one', 'token_sha256': hashlib.sha256(token.encode()).hexdigest(),
              'authorized_by_user_id': str(uuid4()), 'enabled': True,
              'worker_precheck_enabled': True, 'device_ids': [device_id]}
    path = tmp_path / 'grants.json'
    path.write_text(json.dumps({'version': 1, 'clients': [client, client | {'client_id': 'two'}]}), encoding='utf-8')
    with pytest.raises(ApplicationSessionUnavailableError):
        ApplicationAuthenticator(enabled=True, path=path).authenticate('one', token)
