"""Existing ShopSession/HTTP/Signer adapter, without a browser or DB bridge."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import TypeVar
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    EncryptionConfigurationError,
    SecretCipher,
    get_secret_cipher,
)
from app.modules.product_selection.run_contract import (
    SelectionRankQuery,
    SelectionResolvedRequest,
)
from app.modules.sessions.auth_context import ShopSessionAccessor, ShopSessionAuthContext
from app.modules.sessions.collection_readiness import bind_collection_auth_context
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import (
    SessionEncryptionUnavailableError,
    SessionVersionConflictError,
)
from app.modules.sessions.health_service import ShopSessionHealthService
from app.modules.sessions.service import ShopSessionService
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.repository import ShopRepository
from app.platforms.douyin.product_selection import CompassCategoryTree
from app.platforms.douyin.selection_connector import DouyinProductSelectionConnector
from app.platforms.exceptions import (
    PlatformAuthenticationInvalidError,
    PlatformIdentityMismatchError,
)
from app.platforms.registry import create_platform_connectors


T = TypeVar("T")


class SelectionStoredSessionIO:
    def __init__(
        self,
        session_factory: Callable[[], AbstractContextManager[Session]],
        *,
        connector: DouyinProductSelectionConnector | None = None,
        cipher_factory: Callable[[], SecretCipher] = get_secret_cipher,
    ):
        self.session_factory = session_factory
        self.connector = connector or DouyinProductSelectionConnector()
        self.cipher_factory = cipher_factory

    def session_context(self, shop_id: UUID) -> ShopSessionAuthContext:
        with self.session_factory() as session:
            shop = ShopRepository(session).get(shop_id)
            if (
                shop is None
                or shop.platform is not ShopPlatform.DOUYIN
                or shop.platform_shop_id is None
            ):
                raise PlatformIdentityMismatchError()
            try:
                cipher = self.cipher_factory()
            except EncryptionConfigurationError as error:
                raise SessionEncryptionUnavailableError() from error
            accessor = ShopSessionAccessor(session, cipher)

            def finish_owned_read() -> None:
                # This adapter exclusively owns this short-lived Session. End
                # its read transaction before an authoritative identity call.
                if session.new or session.dirty or session.deleted:
                    raise RuntimeError(
                        "Selection Session read boundary contains pending writes",
                    )
                session.rollback()

            health_service = ShopSessionHealthService(
                session,
                accessor,
                create_platform_connectors(),
                session_service=ShopSessionService(session, cipher),
                settings=get_settings(),
                before_platform_io=finish_owned_read,
            )
            health = health_service.check(shop_id, force=False)
            context = accessor.get_auth_context(shop_id, ShopPlatform.DOUYIN)
            return bind_collection_auth_context(
                health,
                context,
                expected_platform=ShopPlatform.DOUYIN,
            )

    def categories(self, context: ShopSessionAuthContext) -> CompassCategoryTree:
        return self._platform_read(
            context,
            lambda: self.connector.categories(context),
        )

    def rank(
        self,
        context: ShopSessionAuthContext,
        request: SelectionResolvedRequest | SelectionRankQuery,
        page_no: int,
    ):
        if page_no not in request.page_numbers:
            raise ValueError("Only approved pages may be requested")
        return self._platform_read(
            context,
            lambda: self.connector.rank(
                context,
                {
                    "page_no": str(page_no),
                    "page_size": str(request.page_size),
                    **request.scope.model_dump(),
                },
            ),
        )

    def basic_info(self, context: ShopSessionAuthContext, product_id: str):
        return self._platform_read(
            context,
            lambda: self.connector.basic_info(context, product_id),
        )

    def _platform_read(
        self,
        context: ShopSessionAuthContext,
        operation: Callable[[], T],
    ) -> T:
        try:
            return operation()
        except PlatformAuthenticationInvalidError:
            self._mark_invalid_if_current(context)
            raise

    def _mark_invalid_if_current(self, context: ShopSessionAuthContext) -> None:
        try:
            cipher = self.cipher_factory()
        except EncryptionConfigurationError:
            # Preserve the authoritative platform error.  A missing local key
            # cannot justify replacing the stored Session status.
            return
        with self.session_factory() as session:
            try:
                ShopSessionAccessor(session, cipher).mark_validation_status(
                    context.shop_id,
                    context.session_version,
                    ShopSessionStatus.INVALID,
                )
            except SessionVersionConflictError:
                # A newer Electron refresh won the race.  Never invalidate it
                # because an older in-flight request was rejected.
                return
