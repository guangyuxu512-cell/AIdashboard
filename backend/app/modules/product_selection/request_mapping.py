"""Observed query mapping and the user-approved bounded Shanghai date policy.

No claim about a platform refresh deadline, captured credentials or automatic
business-error retries. Shop tree validation uses the current authorized read.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.modules.product_selection.exceptions import SelectionRequestUnconfirmedError
from app.modules.product_selection.run_contract import SelectionRunOriginal, SelectionResolvedRequest, SelectionDatePlan
from app.modules.product_selection.schemas import SelectionCategoriesRead
from app.modules.product_selection.source import SelectionSourceScope


def validate_preparable_short_video_choice(original: SelectionRunOriginal) -> None:
    """Reject choices which cannot be represented by the observed query.

    Nonzero path IDs are only a structural precondition, not proof that the
    selected path belongs to the current authorized shop's actual tree.
    """
    unsupported = None
    if original.channel != "short-video":
        unsupported = "CHANNEL_UNCONFIRMED"
    elif original.period != "7d":
        unsupported = "PERIOD_UNCONFIRMED"
    elif original.brand != "all":
        unsupported = "BRAND_UNCONFIRMED"
    elif original.price_mode != "all":
        unsupported = "PRICE_UNCONFIRMED"
    elif (
        not original.industry_id.strip("0")
        or original.industry_id in original.category_ids
        or any(not value.strip("0") for value in original.category_ids)
        or len(set(original.category_ids)) != len(original.category_ids)
    ):
        unsupported = "CATEGORY_PATH_UNCONFIRMED"
    if unsupported is not None:
        raise SelectionRequestUnconfirmedError(details={"reason": unsupported})


def prepare_short_video_scope(
    original: SelectionRunOriginal, *, period_begin: date, period_end: date,
) -> SelectionSourceScope:
    """Encode a supplied seven-day interval without fixing a relative formula.

    Only default brand/price and an explicit non-all category path are prepared.
    Real-time query evidence is a contrast sample, not an enabled feature.
    This internal helper is not accepted directly by any HTTP submission API.
    """
    validate_preparable_short_video_choice(original)
    if (
        type(period_begin) is not date
        or type(period_end) is not date
        or (period_end - period_begin).days != 6
    ):
        raise SelectionRequestUnconfirmedError(details={"reason": "EXPLICIT_PERIOD_UNCONFIRMED"})
    return SelectionSourceScope(
        industry_id=original.industry_id,
        category_id=",".join(original.category_ids),
        brand_type="-1", price_bin="不限", search_info="",
        rank_data_type="1",
        begin_date=period_begin.strftime("%Y/%m/%d 00:00:00"),
        end_date=period_end.strftime("%Y/%m/%d 00:00:00"),
        date_type="21", activity_id="",
    )


def freeze_short_video_request(original: SelectionRunOriginal, accepted_at: datetime) -> SelectionResolvedRequest:
    """User-approved business policy, not a claim about platform refresh time."""
    validate_preparable_short_video_choice(original)
    if accepted_at.utcoffset() is None:
        raise ValueError("Acceptance time must have a timezone")
    day = accepted_at.astimezone(ZoneInfo("Asia/Shanghai")).date()
    return SelectionResolvedRequest(
        version=3, original=original,
        scope=prepare_short_video_scope(original, period_begin=day - timedelta(days=7), period_end=day - timedelta(days=1)),
        page_numbers=tuple(range(1, (original.rank_to + 9) // 10 + 1)),
        date_plan=SelectionDatePlan(
            accepted_local_date=day,
            backup_scope=prepare_short_video_scope(original, period_begin=day - timedelta(days=8), period_end=day - timedelta(days=2)),
        ),
    )


def validate_shop_category(original: SelectionRunOriginal, tree: SelectionCategoriesRead) -> None:
    """Only actual non-all paths of this authorized shop/industry may execute."""
    if tree.shop_id != original.shop_id or tree.industry_id != original.industry_id:
        raise SelectionRequestUnconfirmedError(details={"reason": "CATEGORY_SHOP_MISMATCH"})
    # cate_list may include its industry as the outer display node. The
    # observed rank query supplies that ID only through industry_id; traverse
    # its children for membership without silently rewriting the submitted path.
    industry = next((node for node in tree.nodes if node.category_id == tree.industry_id), None)
    nodes = industry.children if industry is not None else tree.nodes
    for category_id in original.category_ids:
        node = next((node for node in nodes if node.category_id == category_id), None)
        if node is None:
            raise SelectionRequestUnconfirmedError(details={"reason": "CATEGORY_PATH_UNCONFIRMED"})
        nodes = node.children
