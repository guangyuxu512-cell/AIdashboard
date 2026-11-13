from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.api_tokens.models import ApiToken, ApiTokenEvent


class ApiTokenRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, token: ApiToken) -> None:
        self.session.add(token)

    def add_event(self, event: ApiTokenEvent) -> None:
        self.session.add(event)

    def by_hash(self, token_hash: str) -> ApiToken | None:
        return self.session.scalar(select(ApiToken).where(ApiToken.token_hash == token_hash))

    def get(self, token_id: UUID) -> ApiToken | None:
        return self.session.get(ApiToken, token_id)

    def list(self) -> list[ApiToken]:
        return list(self.session.scalars(select(ApiToken).order_by(ApiToken.created_at.desc(), ApiToken.token_id.desc())))

    def list_events(self, token_id: UUID) -> list[ApiTokenEvent]:
        return list(self.session.scalars(select(ApiTokenEvent).where(ApiTokenEvent.token_id == token_id).order_by(ApiTokenEvent.created_at.desc(), ApiTokenEvent.event_id.desc())))
