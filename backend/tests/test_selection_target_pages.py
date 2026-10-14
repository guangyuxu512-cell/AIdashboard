"""Frozen sparse rank pages; legacy records are never rewritten."""

from datetime import UTC, datetime
import json

import pytest

from app.modules.product_selection.request_mapping import freeze_short_video_request
from app.modules.product_selection.run_contract import SelectionResolvedRequest
from tests.test_selection_request_mapping import _original


@pytest.mark.parametrize("first,last,pages", [
    (1, 1, (1,)), (1, 10, (1,)), (10, 11, (1, 2)), (11, 20, (1, 2)),
    (20, 21, (1, 2, 3)), (21, 30, (1, 3)), (149, 150, (1, 15)),
    (150, 200, (1, 15, 16, 17, 18, 19, 20)), (200, 200, (1, 20)),
])
def test_only_first_probe_and_required_official_pages(first, last, pages):
    request = freeze_short_video_request(_original(rank_from=first, rank_to=last), datetime(2026, 10, 14, tzinfo=UTC))
    assert request.page_numbers == pages
    assert SelectionResolvedRequest.model_validate_json(request.model_dump_json()) == request
    assert len(pages) == len(set(pages))
    assert request.original.rank_from == first and request.original.rank_to == last


@pytest.mark.parametrize("period", ["realtime", "1d", "7d", "30d"])
@pytest.mark.parametrize("brand", ["all", "known", "unknown"])
@pytest.mark.parametrize("price", [False, True])
def test_sparse_pages_preserve_date_brand_price_and_old_reader(period, brand, price):
    bounds = {"price_mode": "custom", "price_above": "20", "price_below": "100"} if price else {}
    request = freeze_short_video_request(_original(period=period, brand=brand, rank_from=150, rank_to=200, **bounds), datetime(2026, 12, 31, 16, tzinfo=UTC))
    assert request.version == 8 and request.page_numbers == (1, 15, 16, 17, 18, 19, 20)
    legacy = request.legacy_paging_request()
    serialized, fingerprint = legacy.model_dump_json(), legacy.fingerprint()
    assert legacy.version in {3, 4, 5, 6, 7} and legacy.page_numbers == tuple(range(1, 21))
    assert legacy.scope == request.scope and legacy.date_plan == request.date_plan
    assert SelectionResolvedRequest.model_validate_json(serialized).fingerprint() == fingerprint
    assert legacy.model_dump_json() == serialized
    assert request.fingerprint() != fingerprint
    # Planning/serialization never substitutes other conditions or query dates.
    for pages in ([15, 16, 17, 18, 19, 20], [1, 2, 15, 16, 17, 18, 19, 20], [1, 16, 15, 17, 18, 19, 20], [1, 15, 15, 16, 17, 18, 19, 20]):
        with pytest.raises(ValueError):
            SelectionResolvedRequest.model_validate(json.loads(request.model_dump_json()) | {"page_numbers": pages})
