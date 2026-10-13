"""Observed query mapping and the user-approved bounded Shanghai date policy.

No claim about a platform refresh deadline, captured credentials or automatic
business-error retries. Shop tree validation uses the current authorized read.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.modules.product_selection.exceptions import SelectionRequestUnconfirmedError, SelectionPriceRangeInvalidError
from app.modules.product_selection.run_contract import SelectionRunOriginal, SelectionResolvedRequest, SelectionDatePlan, SelectionRealtimeDatePlan, HISTORICAL_PERIOD_RULES, custom_price_bin
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
    elif original.period not in {"realtime", "7d", *HISTORICAL_PERIOD_RULES}:
        unsupported = "PERIOD_UNCONFIRMED"
    elif original.brand != "all":
        unsupported = "BRAND_UNCONFIRMED"
    elif original.price_mode == "custom":
        try:
            custom_price_bin(original)
        except ValueError:
            raise SelectionPriceRangeInvalidError() from None
    if unsupported is None and (
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
    """Encode confirmed relative period windows and exact platform date enums.

    Only default brand and confirmed unlimited/two-sided price are prepared.
    History 1d/30d uses 20/23; realtime and seven-day retain 1/21.
    This internal helper is not accepted directly by any HTTP submission API.
    """
    validate_preparable_short_video_choice(original)
    span = {"realtime": 0, "7d": 6, **{key: rule[0] - 1 for key, rule in HISTORICAL_PERIOD_RULES.items()}}[original.period]
    if (
        type(period_begin) is not date
        or type(period_end) is not date
        or (period_end - period_begin).days != span
    ):
        raise SelectionRequestUnconfirmedError(details={"reason": "EXPLICIT_PERIOD_UNCONFIRMED"})
    return SelectionSourceScope(
        industry_id=original.industry_id,
        category_id=",".join(original.category_ids),
        brand_type="-1", price_bin=custom_price_bin(original) if original.price_mode == "custom" else "不限", search_info="",
        rank_data_type="1",
        begin_date=period_begin.strftime("%Y/%m/%d 00:00:00"),
        end_date=period_end.strftime("%Y/%m/%d 00:00:00"),
        date_type=(HISTORICAL_PERIOD_RULES[original.period][1] if original.period in HISTORICAL_PERIOD_RULES else "1" if original.period == "realtime" else "21"), activity_id="",
    )


def freeze_short_video_request(original: SelectionRunOriginal, accepted_at: datetime) -> SelectionResolvedRequest:
    """User-approved business policy, not a claim about platform refresh time."""
    validate_preparable_short_video_choice(original)
    if accepted_at.utcoffset() is None:
        raise ValueError("Acceptance time must have a timezone")
    day = accepted_at.astimezone(ZoneInfo("Asia/Shanghai")).date()
    if original.price_mode == "custom":
        # Reuse the frozen date policy, not another execution/request path.
        base = freeze_short_video_request(original.model_copy(update={"price_mode": "all", "price_above": None, "price_below": None}), accepted_at)
        price = custom_price_bin(original)
        plan = base.date_plan
        if isinstance(plan, SelectionDatePlan):
            plan = plan.model_copy(update={"backup_scope": plan.backup_scope.model_copy(update={"price_bin": price})})
        return SelectionResolvedRequest(
            version=6, original=original, scope=base.scope.model_copy(update={"price_bin": price}),
            page_numbers=base.page_numbers, date_plan=plan,
        )
    if original.period == "realtime":
        return SelectionResolvedRequest(
            version=4, original=original,
            scope=prepare_short_video_scope(original, period_begin=day, period_end=day),
            page_numbers=tuple(range(1, (original.rank_to + 9) // 10 + 1)),
            date_plan=SelectionRealtimeDatePlan(accepted_local_date=day),
        )
    if original.period in HISTORICAL_PERIOD_RULES:
        days = HISTORICAL_PERIOD_RULES[original.period][0]
        return SelectionResolvedRequest(
            version=5, original=original,
            scope=prepare_short_video_scope(original, period_begin=day - timedelta(days=days), period_end=day - timedelta(days=1)),
            page_numbers=tuple(range(1, (original.rank_to + 9) // 10 + 1)),
            date_plan=SelectionRealtimeDatePlan(accepted_local_date=day),
        )
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
    if tree.shop_id != original.shop_id:
        raise SelectionRequestUnconfirmedError(details={"reason": "CATEGORY_SHOP_MISMATCH"})
    # The scalar is the shop's default selection, not an industry whitelist.
    # A wrapped tree contains that industry root and all other returned roots;
    # match the submitted root dynamically and exclude it from category_id.
    wrapped = any(node.category_id == tree.industry_id for node in tree.nodes)
    if wrapped:
        industry = next((node for node in tree.nodes if node.category_id == original.industry_id), None)
        if industry is None:
            raise SelectionRequestUnconfirmedError(details={"reason": "CATEGORY_PATH_UNCONFIRMED"})
        nodes = industry.children
    else:
        # Preserve the previously supported unwrapped, single-industry shape.
        if tree.industry_id != original.industry_id:
            raise SelectionRequestUnconfirmedError(details={"reason": "CATEGORY_SHOP_MISMATCH"})
        nodes = tree.nodes
    for category_id in original.category_ids:
        node = next((node for node in nodes if node.category_id == category_id), None)
        if node is None:
            raise SelectionRequestUnconfirmedError(details={"reason": "CATEGORY_PATH_UNCONFIRMED"})
        nodes = node.children
