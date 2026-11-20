import hashlib
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.tasks.exceptions import TaskStateConflictError
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import TaskService


class Session:
    def __init__(self, existing):
        self.existing = existing
        self.locks = 0
        self.commits = 0

    def execute(self, _statement):
        self.locks += 1

    def scalar(self, _statement):
        return self.existing

    def commit(self):
        self.commits += 1


def test_replayed_selection_submission_returns_the_original_task_without_creating_another():
    device_id, team_id, user_id, correlation = uuid4(), uuid4(), uuid4(), uuid4()
    data = TaskCreate(target_device_id=device_id, local_shop_ids=['local-a'],
                      skill_id='douyin.compass_selection', input={'operation': 'categories', 'correlation_id': str(correlation)})
    digest = hashlib.sha256(json.dumps(data.model_dump(mode='json'), ensure_ascii=False, sort_keys=True,
                                      separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    existing = SimpleNamespace(team_id=team_id, created_by_user_id=user_id,
                               input_json={'_operations_request_hash': digest})
    session = Session(existing)
    allowed = []
    authorization = SimpleNamespace(require_execution_resources=lambda **kwargs: allowed.append(kwargs))
    service = TaskService(session, repository=object(), settings=object(), asset_repository=object(),
                          team_authorization_service=authorization)
    actor = SimpleNamespace(user_id=user_id, require_team_id=lambda: team_id)
    assert service.create(data, actor) is existing
    assert session.locks == 1 and session.commits == 1
    assert allowed == [{'team_id': team_id, 'device_id': device_id}]
    with pytest.raises(TaskStateConflictError):
        service.create(data.model_copy(update={'target_device_id': uuid4()}), actor)
