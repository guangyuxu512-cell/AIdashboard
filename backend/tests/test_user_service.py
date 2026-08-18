from uuid import uuid4

import pytest

from app.modules.users.exceptions import UserNotFoundError
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate, UserUpdate
from app.modules.users.service import UserService
from tests.support import FakeSession


class FakeUserRepository:
    def __init__(self) -> None:
        self.items: dict[object, User] = {}

    def list(self, *, offset: int, limit: int) -> list[User]:
        return list(self.items.values())[offset : offset + limit]

    def count(self) -> int:
        return len(self.items)

    def get(self, user_id: object) -> User | None:
        return self.items.get(user_id)

    def add(self, user: User) -> None:
        if user.user_id is None:
            user.user_id = uuid4()
        self.items[user.user_id] = user


def test_user_create_get_list_update_and_not_found() -> None:
    session = FakeSession()
    repository = FakeUserRepository()
    service = UserService(session, repository)  # type: ignore[arg-type]

    created = service.create(UserCreate(display_name="负责人"))
    fetched = service.get(created.user_id)
    items, total = service.list(offset=0, limit=20)
    updated = service.update(created.user_id, UserUpdate(enabled=False))

    assert fetched is created
    assert items == [created]
    assert total == 1
    assert updated.enabled is False

    with pytest.raises(UserNotFoundError):
        service.get(uuid4())
