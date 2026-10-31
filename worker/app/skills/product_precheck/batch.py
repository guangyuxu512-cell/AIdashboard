"""Bounded in-process execution of a product batch across authorized shops.

This module does not fetch credentials or call the platform. A future registered
Skill supplies the authorized platform operation and persists its own results.
"""
from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar
from uuid import UUID


T = TypeVar("T")


@dataclass(frozen=True)
class ProductRevision:
    product_id: str
    revision: str

    def __post_init__(self) -> None:
        if not self.product_id.strip() or not self.revision.strip():
            raise ValueError("product_id and revision are required")


@dataclass(frozen=True)
class BatchItemResult(Generic[T]):
    product: ProductRevision
    shop_id: UUID
    # completed means the callback returned; it does not mean platform approval.
    status: Literal["completed", "failed"]
    value: T | None = None
    error_code: str | None = None


async def run_batch(
    products: Sequence[ProductRevision],
    shop_ids: Sequence[UUID],
    operation: Callable[[UUID, ProductRevision], Awaitable[T]],
    *,
    per_shop_limit: int,
    global_limit: int,
) -> list[BatchItemResult[T]]:
    """Assign every product once, keep per-shop order, and return input order.

    The callback decides how to classify a platform response. Exceptions are
    recorded as a fixed non-secret code; other products continue. Cancellation
    propagates so stopping the enclosing task does not falsely complete it.
    """
    if not shop_ids or len(set(shop_ids)) != len(shop_ids):
        raise ValueError("shop_ids must be nonempty and unique")
    if not 1 <= per_shop_limit <= 5 or not 1 <= global_limit <= 25:
        raise ValueError("concurrency limits must be within 1-5 per shop and 1-25 overall")
    if len({product.product_id for product in products}) != len(products):
        raise ValueError("product_ids must be unique within a batch")

    queues: dict[UUID, deque[tuple[int, ProductRevision]]] = {
        shop_id: deque() for shop_id in shop_ids
    }
    for position, product in enumerate(products):
        queues[shop_ids[position % len(shop_ids)]].append((position, product))

    semaphore = asyncio.Semaphore(global_limit)
    results: list[BatchItemResult[T] | None] = [None] * len(products)

    async def work(shop_id: UUID) -> None:
        queue = queues[shop_id]
        while queue:
            position, product = queue.popleft()
            async with semaphore:
                try:
                    value = await operation(shop_id, product)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    # Platform exceptions may contain cookies, URLs or tokens.
                    results[position] = BatchItemResult(
                        product=product, shop_id=shop_id, status="failed",
                        error_code="PRECHECK_EXECUTION_FAILED",
                    )
                else:
                    results[position] = BatchItemResult(
                        product=product, shop_id=shop_id, status="completed", value=value,
                    )

    async with asyncio.TaskGroup() as group:
        for shop_id, queue in queues.items():
            for _ in range(min(per_shop_limit, len(queue))):
                group.create_task(work(shop_id))
    # Every product was enqueued once and each worker records an outcome.
    if any(result is None for result in results):
        raise RuntimeError("batch finished without recording every product")
    return [result for result in results if result is not None]
