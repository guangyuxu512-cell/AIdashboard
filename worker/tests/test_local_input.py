from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.contracts import WorkerTask
from app.local_input import LocalInputPreparationError, ensure_images_directory


def test_images_directory_is_created_without_clearing_existing_files(tmp_path):
    directory = tmp_path / 'images'
    ensure_images_directory(directory)
    previous = directory / 'previous.jpg'
    previous.write_bytes(b'fixture')
    ensure_images_directory(directory)
    assert previous.read_bytes() == b'fixture'


def test_images_directory_rejects_a_file(tmp_path):
    target = tmp_path / 'file'
    target.write_text('fixture', encoding='utf8')
    with pytest.raises(LocalInputPreparationError):
        ensure_images_directory(target)


def test_worker_rejects_central_account_payload():
    with pytest.raises(ValidationError):
        WorkerTask.model_validate({'task_id': str(uuid4()), 'skill_id': 'system.echo',
            'input': {}, 'lease_until': datetime.now(UTC).isoformat(), 'accounts': [{'shop_id': 'fixture'}]})
