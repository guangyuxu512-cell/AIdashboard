import asyncio
from collections.abc import Awaitable, Callable
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
    ApplicationMerchantIdentityUnverifiedError,
    ApplicationMerchantValidationUnavailableError,
    ApplicationShopNotFoundError,
)
from app.modules.sessions.application_contract import (
    ApplicationCookie,
    ApplicationSessionRead,
    ApplicationShopRead,
)
from app.modules.sessions.application_repository import ApplicationSessionRepository
from app.modules.sessions.auth_context import ShopSessionAccessor, ShopSessionAuthContext
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import ShopSessionNotConfiguredError, ShopSessionPayloadInvalidError
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.merchant_identity import (
    MERCHANT_VERIFICATION_TOTAL_SECONDS,
    MerchantIdentityUnverified,
    MerchantValidationUnavailable,
    verify_merchant_session,
)


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
        merchant_verifier: Callable[[ShopSessionAuthContext, str], Awaitable[None]] = verify_merchant_session,
    ) -> None:
        self.session = session
        self.authenticator = authenticator
        self.repository = repository or ApplicationSessionRepository(session)
        self.accessor = accessor
        self.cipher = cipher
        self.audit = audit or AuditLogService(session)
        self.merchant_verifier = merchant_verifier

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

    def list_shops(
        self, principal: ApplicationPrincipal, *, merchant: bool = False,
    ) -> list[ApplicationShopRead]:
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
                    **({"session_version": (
                        version if status is not None and status is not ShopSessionStatus.NOT_CONFIGURED else None
                    )} if merchant else {}),
                )
                for shop, status, version in rows if shop.shop_id in current.shop_ids
            ]
        except DBAPIError as error:
            self._raise_if_busy(error)
            raise

    def read_session(
        self, principal: ApplicationPrincipal, *, shop_id: UUID, request_id: str,
        merchant: bool = False,
    ) -> ApplicationSessionRead:
        try:
            return self._read_session(
                principal, shop_id=shop_id, request_id=request_id, merchant=merchant,
            )
        except DBAPIError as error:
            self._raise_if_busy(error)
            raise

    def _raise_if_busy(self, error: DBAPIError) -> None:
        if getattr(error.orig, "sqlstate", None) == "55P03":
            self.session.rollback()
            raise ApplicationSessionBusyError() from None

    def _read_session(
        self, principal: ApplicationPrincipal, *, shop_id: UUID, request_id: str,
        merchant: bool,
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
            if merchant:
                raise ApplicationMerchantIdentityUnverifiedError()
            raise ShopSessionPayloadInvalidError()
        if merchant:
            if shop.platform is not ShopPlatform.DOUYIN:
                raise ApplicationMerchantIdentityUnverifiedError()
            # Save only immutable comparison facts, then release every DB row
            # lock before the bounded platform requests. The verifier uses the
            # exact candidate below and never persists response updates.
            expected_platform = shop.platform
            expected_shop_id = shop.platform_shop_id
            expected_version = stored.version
            expected_status = stored.status
            expected_payload = bytes(stored.payload_encrypted)
            self.session.rollback()
            try:
                asyncio.run(asyncio.wait_for(
                    self.merchant_verifier(context, expected_shop_id),
                    timeout=MERCHANT_VERIFICATION_TOTAL_SECONDS,
                ))
            except MerchantIdentityUnverified:
                raise ApplicationMerchantIdentityUnverifiedError() from None
            except (MerchantValidationUnavailable, TimeoutError):
                raise ApplicationMerchantValidationUnavailableError() from None
            except Exception:
                raise ApplicationMerchantValidationUnavailableError() from None

            # A valid result is scoped to the snapshot and grant actually
            # probed. Any concurrent edit, revocation or disable fails closed.
            self.authenticator.reauthorize(principal, shop_id)
            authorizer = self._authorizer(principal)
            shop = self.repository.lock_shop(shop_id)
            if shop is None:
                raise ApplicationShopNotFoundError()
            stored = self.repository.lock_session(shop_id)
            if stored is None:
                raise ShopSessionNotConfiguredError()
            if (
                shop.platform != expected_platform
                or shop.platform_shop_id != expected_shop_id
                or stored.version != expected_version
                or stored.status != expected_status
                or bytes(stored.payload_encrypted) != expected_payload
            ):
                raise ApplicationSessionBusyError()
            context = accessor.get_auth_context(shop_id, shop.platform)
            if (
                context.identity is None
                or context.identity.platform != shop.platform
                or context.identity.platform_shop_id != expected_shop_id
                or context.session_version != expected_version
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
