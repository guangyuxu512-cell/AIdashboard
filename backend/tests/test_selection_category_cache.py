"""Synthetic cache contract: no database, Session or platform requests."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from uuid import uuid4

import pytest

from app.modules.product_selection.category_cache import CATEGORY_CACHE_TTL_SECONDS, SelectionCategoryCache
from app.modules.product_selection.schemas import SelectionCategoriesRead, SelectionCategoryRead
from app.modules.shops.enums import ShopPlatform


def _tree(shop_id, name="tree"):
    return SelectionCategoriesRead(shop_id=shop_id, nodes=[SelectionCategoryRead(category_id="7", name=name, children=[])], industry_id="7", industry_name=None, selected_category_id=None)


def test_24_hour_expiry_and_explicit_refresh_with_detached_results():
    now, shop_id, calls = [0.0], uuid4(), []
    cache = SelectionCategoryCache(clock=lambda: now[0])
    key = (ShopPlatform.DOUYIN, shop_id)

    def load():
        calls.append(1)
        return _tree(shop_id, str(len(calls)))

    result = cache.read(key, load)
    result.nodes[0].name = "cannot poison cache"
    now[0] = CATEGORY_CACHE_TTL_SECONDS - 1
    assert cache.read(key, load).nodes[0].name == "1"
    assert len(calls) == 1
    now[0] += 1
    assert cache.read(key, load).nodes[0].name == "2"
    assert cache.read(key, load, refresh=True).nodes[0].name == "3"
    assert len(calls) == 3


def test_shop_and_platform_keys_are_distinct():
    cache, shop_id, other_shop = SelectionCategoryCache(), uuid4(), uuid4()
    platform = next(item for item in ShopPlatform if item != ShopPlatform.DOUYIN)
    assert cache.read((ShopPlatform.DOUYIN, shop_id), lambda: _tree(shop_id, "a")).nodes[0].name == "a"
    assert cache.read((ShopPlatform.DOUYIN, other_shop), lambda: _tree(other_shop, "b")).nodes[0].name == "b"
    assert cache.read((platform, shop_id), lambda: _tree(shop_id, "c")).nodes[0].name == "c"


@pytest.mark.parametrize("refresh", [False, True])
def test_concurrent_reads_and_refreshes_share_one_load(refresh, monkeypatch):
    cache, shop_id = SelectionCategoryCache(), uuid4()
    key, started, finish, calls = (ShopPlatform.DOUYIN, shop_id), Event(), Event(), []
    if refresh:
        cache.read(key, lambda: _tree(shop_id, "old"))

    def load():
        calls.append(1)
        started.set()
        assert finish.wait(5)
        return _tree(shop_id, "fresh")

    with ThreadPoolExecutor(max_workers=3) as pool:
        owner = pool.submit(cache.read, key, load, refresh=refresh)
        assert started.wait(5)
        pending = cache._loading[key]
        original_result, both_waiting, waiters, lock = pending.result, Event(), [], Lock()

        def wait_result(*args, **kwargs):
            with lock:
                waiters.append(1)
                if len(waiters) == 2:
                    both_waiting.set()
            return original_result(*args, **kwargs)

        monkeypatch.setattr(pending, "result", wait_result)
        follower = pool.submit(cache.read, key, load, refresh=refresh)
        normal = pool.submit(cache.read, key, load)
        assert both_waiting.wait(5)
        finish.set()
        assert owner.result(5).nodes[0].name == "fresh"
        assert follower.result(5).nodes[0].name == "fresh"
        assert normal.result(5).nodes[0].name == "fresh"
    assert len(calls) == 1


def test_failed_refresh_does_not_return_old_tree_or_cache_the_error():
    cache, shop_id = SelectionCategoryCache(), uuid4()
    key = (ShopPlatform.DOUYIN, shop_id)
    cache.read(key, lambda: _tree(shop_id, "old"))

    def fail():
        raise RuntimeError("safe synthetic failure")

    with pytest.raises(RuntimeError, match="synthetic"):
        cache.read(key, fail, refresh=True)
    assert cache.read(key, lambda: _tree(shop_id, "recovered")).nodes[0].name == "recovered"
