"""Read-only lookup for preserved historical selection facts."""
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.models import TeamShopAccess
from app.modules.shops.models import Shop


class ShopRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_actor(self, *, actor: ActorContext, shop_id: UUID) -> Shop | None:
        statement = select(Shop).where(Shop.shop_id == shop_id, Shop.deleted_at.is_(None))
        if not actor.is_super_account:
            statement = statement.where(exists(select(TeamShopAccess.team_id).where(
                TeamShopAccess.team_id == actor.require_team_id(),
                TeamShopAccess.shop_id == Shop.shop_id,
            )))
        return self.session.scalar(statement)
