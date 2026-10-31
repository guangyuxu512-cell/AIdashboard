import asyncio
from collections import Counter
from uuid import uuid4

import pytest

from app.skills.product_precheck.batch import ProductRevision, run_batch


def test_one_hundred_products_are_partitioned_once_with_five_by_five_limit():
    async def run():
        shops = [uuid4() for _ in range(5)]
        products = [ProductRevision(str(i), f"rev-{i}") for i in range(100)]
        active, peaks = Counter(), Counter()
        total = peak_total = 0
        all_active = asyncio.Event()

        async def operation(shop_id, product):
            nonlocal total, peak_total
            active[shop_id] += 1
            total += 1
            peaks[shop_id] = max(peaks[shop_id], active[shop_id])
            peak_total = max(peak_total, total)
            if total == 25:
                all_active.set()
            await asyncio.wait_for(all_active.wait(), timeout=3)
            await asyncio.sleep(0)
            total -= 1
            active[shop_id] -= 1
            return product.product_id

        results = await run_batch(products, shops, operation, per_shop_limit=5, global_limit=25)
        assert len(results) == 100
        assert [item.product for item in results] == products
        assert Counter(item.shop_id for item in results) == Counter({shop: 20 for shop in shops})
        assert all(item.status == "completed" for item in results)
        assert peak_total == 25 and all(peaks[shop] == 5 for shop in shops)
    asyncio.run(run())


def test_one_product_failure_does_not_stop_others_or_expose_exception_text():
    async def run():
        shops = [uuid4(), uuid4()]
        products = [ProductRevision(str(i), "v1") for i in range(7)]
        calls = []
        async def operation(shop, product):
            calls.append((shop, product.product_id))
            if product.product_id == "2":
                raise RuntimeError("synthetic-secret")
            return "callback-returned"
        results = await run_batch(products, shops, operation, per_shop_limit=2, global_limit=3)
        assert len(calls) == 7 and len(set(calls)) == 7
        assert [item.status for item in results].count("failed") == 1
        assert results[2].error_code == "PRECHECK_EXECUTION_FAILED"
        assert "synthetic-secret" not in repr(results)
    asyncio.run(run())


@pytest.mark.parametrize("case", [
    "no_shops", "duplicate_shops", "duplicate_products", "bad_limit", "excess_limit",
])
def test_invalid_batch_is_rejected_before_any_callback(case):
    async def run():
        shop = uuid4()
        shops = [] if case == "no_shops" else [shop, shop] if case == "duplicate_shops" else [shop]
        products = [ProductRevision("1", "a")]
        if case == "duplicate_products":
            products.append(ProductRevision("1", "b"))
        async def operation(shop_id, product):
            raise AssertionError("must not run")
        with pytest.raises(ValueError):
            await run_batch(
                products, shops, operation,
                per_shop_limit=0 if case == "bad_limit" else 6 if case == "excess_limit" else 1,
                global_limit=1,
            )
    asyncio.run(run())


def test_cancellation_propagates():
    async def run():
        started = asyncio.Event()
        async def operation(shop, product):
            started.set()
            await asyncio.Event().wait()
        task = asyncio.create_task(run_batch(
            [ProductRevision("1", "v1")], [uuid4()], operation,
            per_shop_limit=1, global_limit=1,
        ))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(run())
