from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.modules.human_auth.models import HumanSession
from app.modules.users.models import User


SessionWithUser = tuple[HumanSession, User | None]


class HumanSessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, human_session: HumanSession) -> None:
        self.session.add(human_session)

    def get_with_user_by_token_hash(
        self,
        token_hash: str,
    ) -> SessionWithUser | None:
        statement = (
            select(HumanSession, User)
            .outerjoin(User, User.user_id == HumanSession.user_id)
            .where(HumanSession.token_hash == token_hash)
        )
        row = self.session.execute(statement).one_or_none()
        if row is None:
            return None
        return row[0], row[1]

    def revoke_by_token_hash(self, token_hash: str, *, revoked_at: datetime) -> int:
        statement = (
            update(HumanSession)
            .where(
                HumanSession.token_hash == token_hash,
                HumanSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        result = cast(CursorResult[Any], self.session.execute(statement))
        return int(result.rowcount or 0)

    def revoke_all_for_user(self, user_id: UUID, *, revoked_at: datetime) -> int:
        statement = (
            update(HumanSession)
            .where(
                HumanSession.user_id == user_id,
                HumanSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        result = cast(CursorResult[Any], self.session.execute(statement))
        return int(result.rowcount or 0)
