"""Process-local, single-flight cache of parsed trees; never credentials or access."""

from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass
from functools import lru_cache
from threading import Lock
from time import monotonic
from uuid import UUID

from app.modules.product_selection.schemas import SelectionCategoriesRead
from app.modules.shops.enums import ShopPlatform


CATEGORY_CACHE_TTL_SECONDS = 24 * 60 * 60
CategoryKey = tuple[ShopPlatform, UUID]


@dataclass(frozen=True)
class _Entry:
    tree: SelectionCategoriesRead
    expires_at: float


class SelectionCategoryCache:
    """Authorization belongs to the service, including every cache hit/waiter."""

    def __init__(self, *, clock: Callable[[], float] = monotonic):
        self._clock = clock
        self._lock = Lock()
        self._entries: dict[CategoryKey, _Entry] = {}
        self._loading: dict[CategoryKey, Future[SelectionCategoriesRead]] = {}

    def read(
        self, key: CategoryKey, load: Callable[[], SelectionCategoriesRead], *,
        refresh: bool = False,
    ) -> SelectionCategoriesRead:
        with self._lock:
            now = self._clock()
            self._entries = {
                cached_key: entry for cached_key, entry in self._entries.items()
                if entry.expires_at > now
            }
            pending = self._loading.get(key)
            owner = pending is None
            if owner:
                if not refresh and key in self._entries:
                    return self._entries[key].tree.model_copy(deep=True)
                # Failed explicit refresh must not silently serve the old tree.
                self._entries.pop(key, None)
                pending = Future()
                self._loading[key] = pending
        assert pending is not None
        if not owner:
            return pending.result().model_copy(deep=True)
        # No database transaction or cache lock surrounds the platform request.
        try:
            tree = load().model_copy(deep=True)
        except BaseException as error:
            with self._lock:
                self._loading.pop(key)
                pending.set_exception(error)
            raise
        with self._lock:
            self._entries[key] = _Entry(tree, self._clock() + CATEGORY_CACHE_TTL_SECONDS)
            self._loading.pop(key)
            pending.set_result(tree)
        return tree.model_copy(deep=True)


@lru_cache(maxsize=1)
def get_selection_category_cache() -> SelectionCategoryCache:
    return SelectionCategoryCache()
