from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.sessions.models import ShopSession
from app.modules.shops.models import Shop
from app.modules.users.models import User


class ApplicationSessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def lock_authorizer(self, user_id: UUID) -> User | None:
        return self.session.scalar(
            select(User).where(User.user_id == user_id).with_for_update(read=True, nowait=True),
        )

    def list_shops(self, shop_ids: tuple[UUID, ...]):
        statement = (
            select(Shop, ShopSession.status)
            .outerjoin(ShopSession, ShopSession.shop_id == Shop.shop_id)
            .where(Shop.shop_id.in_(shop_ids), Shop.enabled.is_(True), Shop.deleted_at.is_(None))
            .order_by(Shop.display_name, Shop.shop_id)
        )
        return list(self.session.execute(statement))

    def lock_shop(self, shop_id: UUID) -> Shop | None:
        return self.session.scalar(
            select(Shop)
            .where(Shop.shop_id == shop_id, Shop.enabled.is_(True), Shop.deleted_at.is_(None))
            .with_for_update(read=True, nowait=True),
        )

    def lock_session(self, shop_id: UUID) -> ShopSession | None:
        return self.session.scalar(
            select(ShopSession)
            .where(ShopSession.shop_id == shop_id)
            .with_for_update(read=True, nowait=True),
        )
