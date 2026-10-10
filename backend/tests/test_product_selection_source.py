import pytest
from pydantic import ValidationError

from app.modules.product_selection.source import SelectionSourceScope


def scope_values() -> dict[str, str]:
    # Explicit synthetic persistence input; not a platform default/enum claim.
    return {
        "industry_id": "7", "category_id": "1000009092,1000009142",
        "brand_type": "-1", "price_bin": "不限", "search_info": "",
        "rank_data_type": "1", "begin_date": "2026/10/02 00:00:00",
        "end_date": "2026/10/08 00:00:00", "date_type": "21", "activity_id": "",
    }


def test_source_hash_is_stable_but_changes_with_business_scope() -> None:
    values = scope_values()
    original = SelectionSourceScope(**values)
    reversed_keys = SelectionSourceScope(**dict(reversed(list(values.items()))))
    assert original.fingerprint() == reversed_keys.fingerprint()
    assert len(original.fingerprint()) == 64
    assert SelectionSourceScope(**(values | {"category_id": "1000009092"})).fingerprint() != original.fingerprint()
    assert original.period_begin.isoformat() == "2026-10-02"
    assert original.context()["business"] == values


@pytest.mark.parametrize("extra", ["cookie", "a_bogus", "msToken", "page_no", "page_size"])
def test_session_tracking_and_pagination_are_not_source_identity(extra: str) -> None:
    with pytest.raises(ValidationError):
        SelectionSourceScope(**(scope_values() | {extra: "synthetic"}))


@pytest.mark.parametrize("dates", [
    {"begin_date": "2026/10/02 01:00:00"},
    {"begin_date": "2026-10-02"},
    {"begin_date": "2026/10/9 00:00:00"},
    {"begin_date": "2026/10/09 00:00:00"},
])
def test_no_implicit_relative_date_or_encoding_conversion(dates) -> None:
    with pytest.raises(ValidationError):
        SelectionSourceScope(**(scope_values() | dates))
