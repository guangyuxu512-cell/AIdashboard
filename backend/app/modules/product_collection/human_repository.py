"""Authorized human-plane persistence for product collection and library reads."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import case, exists, func, or_, select
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.models import TeamShopAccess
from app.modules.product_collection.models import (
    ProductCollectionItem as Item,
    ProductCollectionRequest as CollectionRequest,
    ProductLibraryGroup as Group,
    ProductLibraryProduct as Product,
    ProductLibraryProductVersion as ProductVersion,
)
from app.modules.product_selection.models import (
    ProductSelectionCandidate as Candidate,
    ProductSelectionObservation as Observation,
)
from app.modules.shops.models import Shop


class ProductCollectionHumanRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_submission(
        self,
        *,
        team_id: UUID,
        user_id: UUID,
        submission_key: UUID,
        lock: bool = False,
    ) -> CollectionRequest | None:
        statement = select(CollectionRequest).where(
            CollectionRequest.team_id == team_id,
            CollectionRequest.requested_by_user_id == user_id,
            CollectionRequest.submission_key == submission_key,
        )
        if lock:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def group(self, *, team_id: UUID, group_id: UUID) -> Group | None:
        return self.session.scalar(
            select(Group).where(
                Group.group_id == group_id,
                Group.team_id == team_id,
                Group.archived_at.is_(None),
            ),
        )

    def visible_candidates(
        self,
        *,
        actor: ActorContext,
        candidate_ids: Iterable[UUID],
    ) -> list[Candidate]:
        ids = tuple(set(candidate_ids))
        if not ids:
            return []
        team_id = actor.require_team_id()
        visible_observation = select(Observation.observation_id).join(
            Shop,
            Shop.shop_id == Observation.request_shop_id,
        ).where(
            Observation.candidate_id == Candidate.candidate_id,
            Shop.deleted_at.is_(None),
        )
        if not actor.is_super_account:
            visible_observation = visible_observation.where(
                exists(
                    select(TeamShopAccess.team_id).where(
                        TeamShopAccess.team_id == team_id,
                        TeamShopAccess.shop_id == Observation.request_shop_id,
                    ),
                ),
            )
        statement = select(Candidate).where(
            Candidate.candidate_id.in_(ids),
            Candidate.team_id == team_id,
            exists(visible_observation),
        )
        return list(self.session.scalars(statement.order_by(Candidate.candidate_id)))

    @staticmethod
    def visible_requests(actor: ActorContext):
        return select(CollectionRequest).where(
            CollectionRequest.team_id == actor.require_team_id(),
        )

    def request_for_actor(
        self,
        *,
        actor: ActorContext,
        request_id: UUID,
        lock: bool = False,
    ) -> CollectionRequest | None:
        statement = self.visible_requests(actor).where(
            CollectionRequest.request_id == request_id,
        )
        if lock:
            statement = statement.with_for_update().execution_options(
                populate_existing=True,
            )
        return self.session.scalar(statement)

    def item_for_actor(
        self,
        *,
        actor: ActorContext,
        item_id: UUID,
        lock: bool = False,
    ) -> Item | None:
        statement = select(Item).where(
            Item.item_id == item_id,
            Item.team_id == actor.require_team_id(),
        )
        if lock:
            statement = statement.with_for_update().execution_options(
                populate_existing=True,
            )
        return self.session.scalar(statement)

    def request_items(self, *, team_id: UUID, request_id: UUID) -> list[Item]:
        return list(
            self.session.scalars(
                select(Item)
                .where(Item.team_id == team_id, Item.request_id == request_id)
                .order_by(Item.created_at, Item.item_id),
            ),
        )

    def request_counts(self, *, team_id: UUID, request_id: UUID) -> dict[str, int]:
        row = self.session.execute(
            select(
                func.count(Item.item_id),
                func.count(Item.item_id).filter(
                    Item.state.in_(("pending_dispatch", "dispatching", "dispatched")),
                ),
                func.count(Item.item_id).filter(
                    Item.state.in_(("running", "received", "processing")),
                ),
                func.count(Item.item_id).filter(Item.state == "succeeded"),
                func.count(Item.item_id).filter(Item.state == "failed"),
                func.count(Item.item_id).filter(Item.state == "canceled"),
            ).where(Item.team_id == team_id, Item.request_id == request_id),
        ).one()
        return dict(
            zip(
                ("item_count", "pending_count", "running_count", "succeeded_count", "failed_count", "canceled_count"),
                (int(value or 0) for value in row),
                strict=True,
            ),
        )

    def list_requests(
        self,
        *,
        actor: ActorContext,
        offset: int,
        limit: int,
    ) -> tuple[list[CollectionRequest], int]:
        statement = self.visible_requests(actor)
        total = self.session.scalar(
            select(func.count()).select_from(statement.subquery()),
        ) or 0
        rows = self.session.scalars(
            statement.order_by(
                CollectionRequest.created_at.desc(),
                CollectionRequest.request_id.desc(),
            ).offset(offset).limit(limit),
        ).all()
        return list(rows), int(total)

    def current_product(
        self,
        *,
        team_id: UUID,
        platform: str,
        source_product_id: str,
    ) -> Product | None:
        return self.session.scalar(
            select(Product).where(
                Product.team_id == team_id,
                Product.platform == platform,
                Product.source_product_id == source_product_id,
            ),
        )

    def list_groups(self, *, actor: ActorContext) -> list[Group]:
        return list(
            self.session.scalars(
                select(Group).where(
                    Group.team_id == actor.require_team_id(),
                    Group.archived_at.is_(None),
                ).order_by(Group.name, Group.group_id),
            ),
        )

    @staticmethod
    def visible_products(actor: ActorContext):
        return select(Product).where(Product.team_id == actor.require_team_id())

    def list_products(
        self,
        *,
        actor: ActorContext,
        offset: int,
        limit: int,
        search: str | None,
        group_id: UUID | None,
        ungrouped: bool,
    ) -> tuple[list[Product], int]:
        statement = self.visible_products(actor)
        if search:
            statement = statement.where(
                or_(
                    Product.title.icontains(search, autoescape=True),
                    Product.source_product_id.icontains(search, autoescape=True),
                ),
            )
        if group_id is not None:
            statement = statement.where(Product.group_id == group_id)
        elif ungrouped:
            statement = statement.where(Product.group_id.is_(None))
        total = self.session.scalar(
            select(func.count()).select_from(statement.subquery()),
        ) or 0
        rows = self.session.scalars(
            statement.order_by(Product.updated_at.desc(), Product.product_id.desc())
            .offset(offset).limit(limit),
        ).all()
        return list(rows), int(total)

    def product_for_actor(
        self,
        *,
        actor: ActorContext,
        product_id: UUID,
    ) -> Product | None:
        return self.session.scalar(
            self.visible_products(actor).where(Product.product_id == product_id),
        )

    def product_versions(
        self,
        *,
        team_id: UUID,
        product_id: UUID,
        limit: int = 20,
    ) -> list[ProductVersion]:
        return list(
            self.session.scalars(
                select(ProductVersion).where(
                    ProductVersion.team_id == team_id,
                    ProductVersion.product_id == product_id,
                ).order_by(
                    ProductVersion.captured_at.desc(),
                    ProductVersion.version_id.desc(),
                ).limit(limit),
            ),
        )

    def latest_item_for_product(
        self,
        *,
        team_id: UUID,
        product: Product,
    ) -> Item | None:
        return self.session.scalar(
            select(Item).where(
                Item.team_id == team_id,
                or_(
                    Item.library_product_id == product.product_id,
                    (
                        (Item.platform == product.platform)
                        & (Item.source_product_id == product.source_product_id)
                    ),
                ),
            ).order_by(Item.updated_at.desc(), Item.item_id.desc()).limit(1),
        )
