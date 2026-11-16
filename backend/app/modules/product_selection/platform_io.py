"""Paused selection execution and its preserved, pure request mapping."""

from app.modules.product_selection.exceptions import SelectionExecutionDisabledError
from app.modules.product_selection.run_contract import SelectionRankQuery, SelectionResolvedRequest


def build_rank_query(request: SelectionResolvedRequest | SelectionRankQuery, page_no: int) -> dict[str, str]:
    """Preserve the approved mapping without accessing a Session or platform."""
    if page_no not in request.page_numbers:
        raise ValueError("Only approved pages may be requested")
    return {"page_no": str(page_no), "page_size": str(request.page_size), **request.scope.model_dump()}


class SelectionUnavailableIO:
    """No server-side platform adapter exists while selection is paused."""

    def __init__(self, *_args, **_kwargs):
        pass

    def session_context(self, *_args, **_kwargs):
        raise SelectionExecutionDisabledError()

    def categories(self, *_args, **_kwargs):
        raise SelectionExecutionDisabledError()

    def rank(self, *_args, **_kwargs):
        raise SelectionExecutionDisabledError()

    def basic_info(self, *_args, **_kwargs):
        raise SelectionExecutionDisabledError()
