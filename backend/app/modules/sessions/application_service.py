from uuid import UUID

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.security import SecretCipher, get_secret_cipher
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.audit.enums import AuditAction, AuditTargetType
from app.modules.audit.service import AuditLogService
from app.modules.sessions.application_auth import (
    ApplicationAuthenticationError,
    ApplicationAuthenticator,
    ApplicationPrincipal,
    ApplicationSessionBusyError,
    ApplicationShopNotFoundError,
)
from app.modules.sessions.application_contract import (
    ApplicationCookie,
    ApplicationSessionRead,
    ApplicationShopRead,
)
from app.modules.sessions.application_repository import ApplicationSessionRepository
from app.modules.sessions.auth_context import ShopSessionAccessor
from app.modules.sessions.exceptions import ShopSessionNotConfiguredError, ShopSessionPayloadInvalidError


class ApplicationSessionService:
    """Release one shop session to an explicitly authorized application."""

    def __init__(
        self,
        session: Session,
        authenticator: ApplicationAuthenticator,
        *,
        repository: ApplicationSessionRepository | None = None,
        accessor: ShopSessionAccessor | None = None,
        cipher: SecretCipher | None = None,
        audit: AuditLogService | None = None,
    ) -> None:
        self.session = session
        self.authenticator = authenticator
        self.repository = repository or ApplicationSessionRepository(session)
        self.accessor = accessor
        self.cipher = cipher
        self.audit = audit or AuditLogService(session)

    def _authorizer(self, principal: ApplicationPrincipal) -> ActorContext:
        user = self.repository.lock_authorizer(principal.grant.authorized_by_user_id)
        if user is None or not user.enabled or not user.is_super_account:
            raise ApplicationAuthenticationError()
        return ActorContext(
            user_id=user.user_id,
            user_display_name=user.display_name,
            team_id=None,
            membership_id=None,
            role_code="super_account",
            data_scope=DataScope.ALL,
            is_super_account=True,
        )

    def list_shops(self, principal: ApplicationPrincipal) -> list[ApplicationShopRead]:
        try:
            self._authorizer(principal)
            rows = self.repository.list_shops(principal.grant.shop_ids)
            current = self.authenticator.authenticate(
                principal.grant.client_id, principal.token,
            ).grant
            if current.authorized_by_user_id != principal.grant.authorized_by_user_id:
                raise ApplicationAuthenticationError()
            return [
                ApplicationShopRead(
                    shop_id=shop.shop_id, display_name=shop.display_name,
                    platform=shop.platform, session_status=status,
                )
                for shop, status in rows if shop.shop_id in current.shop_ids
            ]
        except DBAPIError as error:
            self._raise_if_busy(error)
            raise

    def read_session(
        self, principal: ApplicationPrincipal, *, shop_id: UUID, request_id: str,
    ) -> ApplicationSessionRead:
        try:
            return self._read_session(principal, shop_id=shop_id, request_id=request_id)
        except DBAPIError as error:
            self._raise_if_busy(error)
            raise

    def _raise_if_busy(self, error: DBAPIError) -> None:
        if getattr(error.orig, "sqlstate", None) == "55P03":
            self.session.rollback()
            raise ApplicationSessionBusyError() from None

    def _read_session(
        self, principal: ApplicationPrincipal, *, shop_id: UUID, request_id: str,
    ) -> ApplicationSessionRead:
        self.authenticator.reauthorize(principal, shop_id)
        authorizer = self._authorizer(principal)
        shop = self.repository.lock_shop(shop_id)
        if shop is None:
            raise ApplicationShopNotFoundError()
        stored = self.repository.lock_session(shop_id)
        if stored is None:
            raise ShopSessionNotConfiguredError()
        accessor = self.accessor or ShopSessionAccessor(
            self.session, self.cipher or get_secret_cipher(),
        )
        context = accessor.get_auth_context(shop_id, shop.platform)
        if (
            context.identity is None
            or not shop.platform_shop_id
            or context.identity.platform != shop.platform
            or context.identity.platform_shop_id != shop.platform_shop_id
            or context.session_version != stored.version
        ):
            raise ShopSessionPayloadInvalidError()
        result = ApplicationSessionRead(
            shop_id=shop_id,
            platform=context.platform,
            session_version=context.session_version,
            cookies=tuple(
                ApplicationCookie.model_validate(cookie.model_dump())
                for cookie in context.cookies
            ),
        )
        # Auth is distinct from a human login.  The existing audit schema's
        # actor_user_id means the real delegating administrator, while details
        # explicitly identify the application that made this request.
        self.authenticator.reauthorize(principal, shop_id)
        self.audit.record_access_management_action(
            request_id=request_id,
            actor=authorizer,
            action=AuditAction.APPLICATION_READ_SHOP_SESSION,
            target_type=AuditTargetType.SHOP_SESSION,
            target_id=shop_id,
            details={
                "actor_kind": "application",
                "application_id": principal.grant.client_id,
                "authorized_by_user_id": str(authorizer.user_id),
                "session_version": context.session_version,
            },
        )
        # Audit must be durable before any Session can leave the service.
        self.session.commit()
        # Do not deliver if the application credential was revoked during commit.
        self.authenticator.reauthorize(principal, shop_id)
        return result
