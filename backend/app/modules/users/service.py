from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.users.exceptions import UserNotFoundError
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate, UserUpdate


class UserService:
    def __init__(
        self,
        session: Session,
        repository: UserRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or UserRepository(session)

    def list(self, *, offset: int, limit: int) -> tuple[list[User], int]:
        return self.repository.list(offset=offset, limit=limit), self.repository.count()

    def get(self, user_id: UUID) -> User:
        user = self.repository.get(user_id)
        if user is None:
            raise UserNotFoundError()
        return user

    def create(self, data: UserCreate) -> User:
        user = User(**data.model_dump())
        self.repository.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def update(self, user_id: UUID, data: UserUpdate) -> User:
        user = self.get(user_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        self.session.commit()
        self.session.refresh(user)
        return user
