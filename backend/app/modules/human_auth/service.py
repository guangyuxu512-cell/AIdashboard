import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.access.contracts import HumanPrincipal
from app.modules.access.exceptions import (
    HumanAuthenticationRequiredError,
    HumanUserDisabledError,
)
from app.modules.human_auth.exceptions import (
    HumanBootstrapNotAllowedError,
    HumanLoginFailedError,
    HumanLoginNameConflictError,
    HumanSessionInvalidError,
)
from app.modules.human_auth.identifiers import normalize_login_name
from app.modules.human_auth.models import HumanSession
from app.modules.human_auth.passwords import PasswordService
from app.modules.human_auth.repository import HumanSessionRepository
from app.modules.human_auth.schemas import HumanLoginRequest
from app.modules.users.exceptions import UserNotFoundError
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.shared.identifiers import generate_id


SESSION_TOKEN_BYTES = 48


@dataclass(frozen=True, slots=True)
class HumanLoginResult:
    principal: HumanPrincipal
    raw_session_token: str = field(repr=False)
    expires_at: datetime


class HumanAuthService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        password_service: PasswordService,
        *,
        user_repository: UserRepository | None = None,
        session_repository: HumanSessionRepository | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.password_service = password_service
        self.user_repository = user_repository or UserRepository(session)
        self.session_repository = session_repository or HumanSessionRepository(session)

    def login(
        self,
        command: HumanLoginRequest,
        *,
        now: datetime | None = None,
    ) -> HumanLoginResult:
        user = self.user_repository.get_by_login_name(command.login_name)
        raw_password = command.password.get_secret_value()
        if user is None or user.password_hash is None:
            self.password_service.burn_unknown_login_time(raw_password)
            raise HumanLoginFailedError()

        valid, updated_hash = self.password_service.verify_and_update(
            raw_password,
            user.password_hash,
        )
        if not valid:
            raise HumanLoginFailedError()
        if not user.enabled:
            raise HumanUserDisabledError()
        if updated_hash is not None:
            user.password_hash = updated_hash

        issued_at = now or datetime.now(UTC)
        expires_at = issued_at + timedelta(
            seconds=self.settings.human_session_ttl_seconds,
        )
        raw_token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        human_session = HumanSession(
            session_id=generate_id(),
            user_id=user.user_id,
            token_hash=self.hash_token(raw_token),
            expires_at=expires_at,
        )
        self.session_repository.add(human_session)
        self.session.commit()
        return HumanLoginResult(
            principal=self._principal(user),
            raw_session_token=raw_token,
            expires_at=expires_at,
        )

    def resolve_principal(
        self,
        raw_session_token: str | None,
        *,
        now: datetime | None = None,
    ) -> HumanPrincipal:
        if not raw_session_token:
            raise HumanAuthenticationRequiredError()
        stored = self.session_repository.get_with_user_by_token_hash(
            self.hash_token(raw_session_token),
        )
        if stored is None:
            raise HumanSessionInvalidError()
        human_session, user = stored
        current_time = now or datetime.now(UTC)
        expires_at = self._aware_utc(human_session.expires_at)
        if human_session.revoked_at is not None or expires_at <= current_time:
            raise HumanSessionInvalidError()
        if user is None:
            raise HumanSessionInvalidError()
        if not user.enabled:
            raise HumanUserDisabledError()
        return self._principal(user)

    def logout(
        self,
        raw_session_token: str | None,
        *,
        now: datetime | None = None,
    ) -> None:
        if raw_session_token:
            self.session_repository.revoke_by_token_hash(
                self.hash_token(raw_session_token),
                revoked_at=now or datetime.now(UTC),
            )
            self.session.commit()

    def set_credentials(
        self,
        *,
        user_id: UUID,
        login_name: str,
        password: str,
        now: datetime | None = None,
    ) -> User:
        user = self.user_repository.get(user_id)
        if user is None:
            raise UserNotFoundError()
        normalized_login = normalize_login_name(login_name)
        existing = self.user_repository.get_by_login_name(normalized_login)
        if existing is not None and existing.user_id != user_id:
            raise HumanLoginNameConflictError()

        user.login_name = normalized_login
        user.password_hash = self.password_service.hash_password(password)
        self.session_repository.revoke_all_for_user(
            user_id,
            revoked_at=now or datetime.now(UTC),
        )
        self.session.commit()
        self.session.refresh(user)
        return user

    def bootstrap_first_user(
        self,
        *,
        display_name: str,
        login_name: str,
        password: str,
    ) -> User:
        if self.user_repository.count() != 0:
            raise HumanBootstrapNotAllowedError()
        normalized_display_name = display_name.strip()
        if not normalized_display_name or len(normalized_display_name) > 100:
            raise ValueError("显示名称不能为空且不能超过100个字符")
        user = User(
            user_id=generate_id(),
            display_name=normalized_display_name,
            login_name=normalize_login_name(login_name),
            password_hash=self.password_service.hash_password(password),
            enabled=True,
            # The first locally bootstrapped operator is explicitly the one
            # company-level super account.  It deliberately receives no
            # default-Team membership.
            is_super_account=True,
        )
        self.user_repository.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    @staticmethod
    def hash_token(raw_session_token: str) -> str:
        return hashlib.sha256(raw_session_token.encode("utf-8")).hexdigest()

    @staticmethod
    def _principal(user: User) -> HumanPrincipal:
        return HumanPrincipal(
            user_id=user.user_id,
            display_name=user.display_name,
        )

    @staticmethod
    def _aware_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
