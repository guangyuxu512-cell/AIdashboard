from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.access.contracts import HumanPrincipal
from app.modules.access.repository import TeamRepository
from app.modules.api_tokens.exceptions import (ApiTokenInputError, ApiTokenInvalidError,
    ApiTokenNotFoundError, ApiTokenNotRecoverableError, ApiTokenRecoveryUnavailableError)
from app.modules.api_tokens.models import ApiToken, ApiTokenEvent
from app.modules.api_tokens.repository import ApiTokenRepository
from app.modules.audit.models import AuditLog
from app.modules.users.repository import UserRepository
from app.shared.identifiers import generate_id

TOKEN_PREFIX = "ccai_"


@dataclass(frozen=True, slots=True)
class IssuedToken:
    record: ApiToken
    raw_token: str = field(repr=False)


class ApiTokenService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = ApiTokenRepository(session)

    @staticmethod
    def _hash(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate(permissions: list[str], team_ids: list[UUID] | None, expires_at: datetime | None, catalog: list[dict], *, require_future: bool = True) -> tuple[list[str], list[str] | None]:
        known = {item["id"]: item for item in catalog}
        selected = sorted(set(permissions))
        if not selected or any(item not in known for item in selected):
            raise ApiTokenInputError()
        if expires_at is not None and (expires_at.tzinfo is None or (require_future and expires_at <= datetime.now(UTC))):
            raise ApiTokenInputError()
        if team_ids is not None:
            if not team_ids or any(not known[item]["team_scoped"] for item in selected):
                raise ApiTokenInputError()
            return selected, sorted({str(value) for value in team_ids})
        return selected, None

    def _validate_teams(self, team_ids: list[UUID] | None) -> None:
        for team_id in team_ids or []:
            team = TeamRepository(self.session).get(team_id)
            if team is None or not team.enabled:
                raise ApiTokenInputError()

    def _audit(self, actor, request_id: str, action: str, record: ApiToken) -> None:
        self.repository.add_event(ApiTokenEvent(
            request_id=request_id[:128], actor_user_id=actor.user_id,
            action=action, token_id=record.token_id, name=record.name,
        ))

    @staticmethod
    def _recoverable_value(token_id: UUID, recovery_key: str | None) -> str:
        if recovery_key is None or len(recovery_key.encode("utf-8")) < 32:
            raise ApiTokenRecoveryUnavailableError()
        digest = hmac.digest(recovery_key.encode("utf-8"), b"center-api-token-v1\0" + token_id.bytes, "sha256")
        return TOKEN_PREFIX + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def issue(self, *, actor, request_id: str, name: str, permissions: list[str], team_ids: list[UUID] | None, enabled: bool, expires_at: datetime | None, catalog: list[dict], recoverable: bool = False, recovery_key: str | None = None) -> IssuedToken:
        name = name.strip()
        if not name or len(name) > 100:
            raise ApiTokenInputError()
        permissions, team_values = self._validate(permissions, team_ids, expires_at, catalog)
        self._validate_teams(team_ids)
        token_id = generate_id()
        raw = self._recoverable_value(token_id, recovery_key) if recoverable else TOKEN_PREFIX + secrets.token_urlsafe(48)
        record = ApiToken(token_id=token_id, owner_user_id=actor.user_id, name=name, token_hash=self._hash(raw), permissions=permissions, team_ids=team_values, enabled=enabled, expires_at=expires_at)
        self.repository.add(record)
        self.session.flush()
        self._audit(actor, request_id, "create", record)
        self.session.commit()
        self.session.refresh(record)
        return IssuedToken(record, raw)

    def reveal(self, token_id: UUID, *, actor, request_id: str, recovery_key: str | None) -> str:
        record = self.repository.get(token_id)
        if record is None or record.revoked_at is not None:
            raise ApiTokenNotFoundError()
        raw = self._recoverable_value(token_id, recovery_key)
        if not hmac.compare_digest(self._hash(raw), record.token_hash):
            raise ApiTokenNotRecoverableError()
        # The existing token-event table only allows create/update/revoke.
        # Record disclosure in the existing administrative audit log instead.
        self.session.add(AuditLog(request_id=request_id[:128], actor_user_id=actor.user_id,
            action="api_token.reveal", target_type="api_token", target_id=token_id))
        self.session.commit()
        return raw

    def list(self) -> list[ApiToken]:
        return self.repository.list()

    def list_events(self, token_id: UUID) -> list[ApiTokenEvent]:
        if self.repository.get(token_id) is None:
            raise ApiTokenNotFoundError()
        return self.repository.list_events(token_id)

    def update(self, token_id: UUID, *, actor, request_id: str, name: str, permissions: list[str], team_ids: list[UUID] | None, enabled: bool, expires_at: datetime | None, catalog: list[dict]) -> ApiToken:
        record = self.repository.get(token_id)
        if record is None or record.revoked_at is not None:
            raise ApiTokenNotFoundError()
        name = name.strip()
        if not name or len(name) > 100:
            raise ApiTokenInputError()
        permissions, team_values = self._validate(permissions, team_ids, expires_at, catalog, require_future=False)
        if team_values != record.team_ids:
            self._validate_teams(team_ids)
        record.name, record.permissions, record.team_ids, record.enabled, record.expires_at = name, permissions, team_values, enabled, expires_at
        record.updated_at = datetime.now(UTC)
        self._audit(actor, request_id, "update", record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def set_enabled(self, token_id: UUID, *, actor, request_id: str, enabled: bool) -> ApiToken:
        record = self.repository.get(token_id)
        if record is None or record.revoked_at is not None:
            raise ApiTokenNotFoundError()
        if record.enabled != enabled:
            record.enabled = enabled
            record.updated_at = datetime.now(UTC)
            self._audit(actor, request_id, "update", record)
            self.session.commit()
            self.session.refresh(record)
        return record

    def revoke(self, token_id: UUID, *, actor, request_id: str) -> None:
        record = self.repository.get(token_id)
        if record is None:
            raise ApiTokenNotFoundError()
        if record.revoked_at is None:
            record.revoked_at = record.updated_at = datetime.now(UTC)
            self._audit(actor, request_id, "revoke", record)
            self.session.commit()

    def authenticate(self, raw: str) -> HumanPrincipal:
        if not raw.startswith(TOKEN_PREFIX) or len(raw) > 128:
            raise ApiTokenInvalidError()
        record = self.repository.by_hash(self._hash(raw))
        now = datetime.now(UTC)
        expires_at = record.expires_at if record is not None else None
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if record is None or not record.enabled or record.revoked_at is not None or (expires_at is not None and expires_at <= now):
            raise ApiTokenInvalidError()
        owner = UserRepository(self.session).get(record.owner_user_id)
        if owner is None or not owner.enabled or not owner.is_super_account:
            raise ApiTokenInvalidError()
        try:
            team_ids = None if record.team_ids is None else tuple(UUID(item) for item in record.team_ids)
            if not isinstance(record.permissions, list) or any(not isinstance(item, str) for item in record.permissions) or team_ids == ():
                raise ValueError()
        except (ValueError, TypeError):
            raise ApiTokenInvalidError() from None
        return HumanPrincipal(user_id=owner.user_id, display_name=owner.display_name, api_token_id=record.token_id, api_permissions=tuple(record.permissions), api_team_ids=team_ids)
