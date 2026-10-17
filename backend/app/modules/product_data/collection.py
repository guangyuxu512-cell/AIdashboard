"""Finite full-page assembly; only a complete immutable result may be published."""

from collections.abc import Callable
from dataclasses import dataclass

from app.modules.product_data.source import ProductDataSlice
from app.platforms.douyin.product_data import (
    PRODUCT_METRICS,
    CompassProductDataPage,
    CompassProductDataRow,
)
from app.platforms.exceptions import PlatformResponseInvalidError


@dataclass(frozen=True)
class CompleteProductDataSnapshot:
    scope: ProductDataSlice
    products: tuple[CompassProductDataRow, ...]
    total: int
    page_count: int

    @property
    def raw_complete_rows(self) -> int:
        return sum(row.raw_metrics_complete for row in self.products)

    @property
    def display_complete_rows(self) -> int:
        return sum(row.display_metrics_complete for row in self.products)


def collect_complete_snapshot(
    scope: ProductDataSlice,
    fetch_page: Callable[[int], CompassProductDataPage],
    *,
    max_pages: int,
) -> CompleteProductDataSnapshot:
    """Fetch each approved page once, without retry, fallback or storage writes.

    The caller owns Session/actor rechecks, its explicit request budget and all
    persistence. Any exception leaves the existing published generation alone.
    """
    if type(max_pages) is not int or max_pages < 1:
        raise ValueError("An explicit positive page budget is required")
    first = fetch_page(1)
    if first.total < 1 or first.page_size != 10:
        raise _incomplete("first_page_contract")
    pages = (first.total + first.page_size - 1) // first.page_size
    if pages > max_pages:
        raise _incomplete("page_budget_exceeded")
    products: list[CompassProductDataRow] = []
    seen: set[str] = set()
    metric_codes = tuple(item.code for item in PRODUCT_METRICS)
    platform_shop_id: str | None = None
    for page_no in range(1, pages + 1):
        page = first if page_no == 1 else fetch_page(page_no)
        expected_rows = min(10, first.total - (page_no - 1) * 10)
        if (
            page.page_no != page_no or page.page_size != 10
            or page.total != first.total or len(page.products) != expected_rows
        ):
            raise _incomplete("page_coverage_changed")
        for row in page.products:
            if row.product_id in seen:
                raise _incomplete("duplicate_product")
            if platform_shop_id is None:
                platform_shop_id = row.platform_shop_id
            if row.platform_shop_id != platform_shop_id:
                raise _incomplete("shop_identity_changed")
            if tuple(item.definition.code for item in row.metrics) != metric_codes:
                raise _incomplete("metric_contract_changed")
            seen.add(row.product_id)
            products.append(row)
    if len(products) != first.total:
        raise _incomplete("unique_count_mismatch")
    return CompleteProductDataSnapshot(scope, tuple(products), first.total, pages)


def _incomplete(reason: str) -> PlatformResponseInvalidError:
    return PlatformResponseInvalidError(details={
        "failure_stage": "collection_coverage", "reason": reason,
    })
