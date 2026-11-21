from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.workers.precheck_contract import PrecheckInput, supports_full_category_tree
from app.modules.workers.precheck_service import PrecheckUnavailable, _tree_display_all


@pytest.mark.parametrize(("version", "supported"), [
    ("2.0.0", False), ("2.0.1", True), ("2.1.0", True), ("10.0.0", True),
    ("2.0.1-dev", False), ("", False),
])
def test_full_tree_requires_a_compatible_capability(version, supported):
    assert supports_full_category_tree(version) is supported


def test_full_tree_is_explicit_and_tree_only():
    base = {"category_id": "1000005081", "title": "商品"}
    assert PrecheckInput.model_validate({**base, "operation": "tree"}).full_category_tree is False
    assert PrecheckInput.model_validate({**base, "operation": "tree", "full_category_tree": True}).full_category_tree is True
    with pytest.raises(ValidationError):
        PrecheckInput.model_validate({**base, "operation": "schema", "full_category_tree": True})
    with pytest.raises(ValidationError):
        PrecheckInput.model_validate({**base, "operation": "tree", "full_category_tree": "true"})


def test_schema_metadata_is_explicit_and_schema_only():
    base = {"category_id": "1000010274", "title": "商品"}
    assert PrecheckInput.model_validate(base).require_schema_metadata is False
    assert PrecheckInput.model_validate({**base, "require_schema_metadata": True}).require_schema_metadata is True
    with pytest.raises(ValidationError):
        PrecheckInput.model_validate({**base, "operation": "tree", "require_schema_metadata": True})
    with pytest.raises(ValidationError):
        PrecheckInput.model_validate({**base, "require_schema_metadata": "true"})


@pytest.mark.parametrize(("version", "expected"), [("2.0.0", None), ("2.0.1", "1"), (None, None)])
def test_signing_cannot_downgrade_a_full_tree_request(version, expected):
    class Session:
        def get(self, model, key):
            return SimpleNamespace(skill_version=version) if version else None

    session = Session()
    device = uuid4()
    assert _tree_display_all(session, device, SimpleNamespace(input_json={})) == "0"
    full = SimpleNamespace(input_json={"_full_category_tree": True})
    if expected is None:
        with pytest.raises(PrecheckUnavailable):
            _tree_display_all(session, device, full)
    else:
        assert _tree_display_all(session, device, full) == expected
