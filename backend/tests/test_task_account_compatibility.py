import pytest

from app.modules.tasks.service import _supports_task_account_shop_name


@pytest.mark.parametrize(
    ("worker_version", "expected"),
    [
        (None, False),
        ("", False),
        ("0.4.6", False),
        ("0.4.7", True),
        ("0.4.7+win", True),
        ("0.5.0", True),
        ("invalid", False),
    ],
)
def test_shop_name_is_only_sent_to_compatible_worker_versions(
    worker_version: str | None,
    expected: bool,
) -> None:
    assert _supports_task_account_shop_name(worker_version) is expected
