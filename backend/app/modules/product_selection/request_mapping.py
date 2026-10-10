"""Prepare observed business parameters; this is not an enabled date resolver.

The caller must supply an independently confirmed explicit interval. Nothing
here derives dates from a clock, validates a live category tree, plans pages,
or enables a submission. The public resolver stays closed until those rules
are frozen. No captured authentication or tracking parameter is accepted.
"""

from datetime import date

from app.modules.product_selection.exceptions import SelectionRequestUnconfirmedError
from app.modules.product_selection.run_contract import SelectionRunOriginal
from app.modules.product_selection.source import SelectionSourceScope


def validate_preparable_short_video_choice(original: SelectionRunOriginal) -> None:
    """Reject choices which cannot be represented by the observed query.

    Nonzero path IDs are only a structural precondition, not proof that a
    selected category is a current authorized shop's actual leaf category.
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
    elif original.first_listed_only:
        unsupported = "FIRST_LISTED_FILTER_UNCONFIRMED"
    elif (
        not original.industry_id.strip("0")
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
