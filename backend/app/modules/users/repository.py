from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.users.models import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, *, offset: int, limit: int) -> list[User]:
        statement = select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
        return list(self.session.scalars(statement))

    def count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(User)) or 0

    def get(self, user_id: UUID) -> User | None:
        return self.session.get(User, user_id)

    def add(self, user: User) -> None:
        self.session.add(user)
