"""Authorized, explicit category read; transactions never surround platform I/O."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.product_selection.category_cache import (
    SelectionCategoryCache, get_selection_category_cache,
)
from app.modules.product_selection.platform_io import SelectionStoredSessionIO
from app.modules.product_selection.schemas import SelectionCategoriesRead, SelectionCategoryRead
from app.modules.product_selection.service import ProductSelectionFactService
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.product_selection import CompassCategoryNode


def _node(node: CompassCategoryNode) -> SelectionCategoryRead:
    return SelectionCategoryRead(
        category_id=node.category_id, name=node.name,
        children=[_node(child) for child in node.children],
    )


class SelectionCategoryService:
    def __init__(
        self, session_factory: Callable[[], AbstractContextManager[Session]], *,
        platform: SelectionStoredSessionIO | None = None,
        cache: SelectionCategoryCache | None = None,
    ):
        self.session_factory = session_factory
        self.platform = platform or SelectionStoredSessionIO(session_factory)
        self.cache = cache if cache is not None else get_selection_category_cache()

    def _authorize(self, actor: ActorContext, shop_id: UUID):
        with self.session_factory() as session:
            facts = ProductSelectionFactService(session)
            current = facts._current_actor(actor)
            facts._execution_shop(current, shop_id)

    def read(
        self, actor: ActorContext, shop_id: UUID, *, refresh: bool = False,
    ) -> SelectionCategoriesRead:
        self._authorize(actor, shop_id)

        def load() -> SelectionCategoriesRead:
            return self._load(actor, shop_id)

        tree = self.cache.read((ShopPlatform.DOUYIN, shop_id), load, refresh=refresh)
        # Hits and single-flight waiters still recheck current Team/module/Shop.
        self._authorize(actor, shop_id)
        return tree

    def _load(self, actor: ActorContext, shop_id: UUID) -> SelectionCategoriesRead:
        context = self.platform.session_context(shop_id)
        if context.shop_id != shop_id:
            from app.platforms.exceptions import PlatformIdentityMismatchError
            raise PlatformIdentityMismatchError()
        self._authorize(actor, shop_id)
        tree = self.platform.categories(context)
        # Revoked access cannot receive an already-returned category tree.
        self._authorize(actor, shop_id)
        return SelectionCategoriesRead(
            shop_id=shop_id, nodes=[_node(node) for node in tree.nodes],
            industry_id=tree.industry_id, industry_name=tree.industry_name,
            selected_category_id=tree.selected_category_id,
        )
