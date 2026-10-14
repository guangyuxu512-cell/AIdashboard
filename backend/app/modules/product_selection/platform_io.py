"""Existing ShopSession/HTTP/Signer adapter, without a browser or DB bridge."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import SecretCipher, get_secret_cipher, EncryptionConfigurationError
from app.modules.product_selection.run_contract import SelectionResolvedRequest, SelectionRankQuery
from app.modules.sessions.auth_context import ShopSessionAccessor, ShopSessionAuthContext
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import (
    ShopSessionAuthenticationInvalidError, ShopSessionNotConfiguredError,
    SessionEncryptionUnavailableError,
)
from app.modules.sessions.service import ShopSessionService
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.repository import ShopRepository
from app.platforms.douyin.product_selection import CompassCategoryTree
from app.platforms.douyin.selection_connector import DouyinProductSelectionConnector
from app.platforms.exceptions import PlatformIdentityMismatchError


class SelectionStoredSessionIO:
    def __init__(
        self, session_factory: Callable[[], AbstractContextManager[Session]], *,
        connector: DouyinProductSelectionConnector | None = None,
        cipher_factory: Callable[[], SecretCipher] = get_secret_cipher,
    ):
        self.session_factory = session_factory
        self.connector = connector or DouyinProductSelectionConnector()
        self.cipher_factory = cipher_factory

    def session_context(self, shop_id: UUID) -> ShopSessionAuthContext:
        with self.session_factory() as session:
            # No identity network request is introduced for every rank/basic
            # call. Existing capture/validation owns identity verification.
            shop = ShopRepository(session).get(shop_id)
            if shop is None or shop.platform_shop_id is None:
                raise PlatformIdentityMismatchError()
            metadata = ShopSessionService(session).get_metadata(shop_id)
            if not metadata.configured:
                raise ShopSessionNotConfiguredError()
            if metadata.status != ShopSessionStatus.VALID or (
                metadata.expires_at is not None and metadata.expires_at <= datetime.now(UTC)
            ):
                raise ShopSessionAuthenticationInvalidError()
            try:
                cipher = self.cipher_factory()
            except EncryptionConfigurationError as error:
                raise SessionEncryptionUnavailableError() from error
            return ShopSessionAccessor(session, cipher).get_auth_context(shop_id, ShopPlatform.DOUYIN)

    def categories(self, context: ShopSessionAuthContext) -> CompassCategoryTree:
        return self.connector.categories(context)

    def rank(self, context: ShopSessionAuthContext, request: SelectionResolvedRequest | SelectionRankQuery, page_no: int):
        if page_no not in request.page_numbers:
            raise ValueError("Only approved pages may be requested")
        return self.connector.rank(context, {
            "page_no": str(page_no), "page_size": str(request.page_size),
            **request.scope.model_dump(),
        })

    def basic_info(self, context: ShopSessionAuthContext, product_id: str):
        return self.connector.basic_info(context, product_id)
