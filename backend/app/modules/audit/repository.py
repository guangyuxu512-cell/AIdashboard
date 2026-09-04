from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog
from app.modules.users.models import User


AuditLogWithActor = tuple[AuditLog, str]


class AuditLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, audit_log: AuditLog) -> None:
        self.session.add(audit_log)

    def list(
        self,
        *,
        offset: int,
        limit: int,
        created_from: datetime | None,
        created_to: datetime | None,
        actor_user_id: UUID | None,
        action: str | None,
    ) -> tuple[list[AuditLogWithActor], int]:
        filters = self._filters(
            created_from=created_from,
            created_to=created_to,
            actor_user_id=actor_user_id,
            action=action,
        )
        statement = (
            select(AuditLog, User.display_name)
            .join(User, User.user_id == AuditLog.actor_user_id)
            .where(*filters)
            .order_by(AuditLog.created_at.desc(), AuditLog.audit_log_id.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = [
            (row[0], row[1])
            for row in self.session.execute(statement)
        ]
        count_statement = (
            select(func.count())
            .select_from(AuditLog)
            .where(*filters)
        )
        return rows, self.session.scalar(count_statement) or 0

    @staticmethod
    def _filters(
        *,
        created_from: datetime | None,
        created_to: datetime | None,
        actor_user_id: UUID | None,
        action: str | None,
    ) -> Sequence[object]:
        filters: list[object] = []
        if created_from is not None:
            filters.append(AuditLog.created_at >= created_from)
        if created_to is not None:
            filters.append(AuditLog.created_at < created_to)
        if actor_user_id is not None:
            filters.append(AuditLog.actor_user_id == actor_user_id)
        if action is not None:
            filters.append(AuditLog.action == action)
        return filters
