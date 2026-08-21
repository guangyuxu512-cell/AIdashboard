from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.notifications.models import NotificationChannel


class NotificationChannelRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[NotificationChannel]:
        return list(
            self.session.scalars(
                select(NotificationChannel).order_by(
                    NotificationChannel.created_at.asc(),
                ),
            ),
        )

    def list_enabled(self) -> list[NotificationChannel]:
        return list(
            self.session.scalars(
                select(NotificationChannel)
                .where(NotificationChannel.enabled.is_(True))
                .order_by(NotificationChannel.created_at.asc()),
            ),
        )

    def get(self, channel_id: UUID) -> NotificationChannel | None:
        return self.session.get(NotificationChannel, channel_id)

    def add(self, channel: NotificationChannel) -> None:
        self.session.add(channel)
