"""Short Session transactions around, never across, a bounded platform page."""

from datetime import timedelta

from app.core.security import EncryptionConfigurationError, get_secret_cipher
from app.modules.product_data.exceptions import ProductDataSessionValidationRequiredError
from app.modules.product_data.service import ProductDataService
from app.modules.sessions.auth_context import ShopSessionAccessor
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import (
    SessionEncryptionUnavailableError, SessionVersionConflictError, ShopSessionNotConfiguredError,
    ShopSessionAuthenticationInvalidError,
)
from app.modules.sessions.health_service import ShopSessionHealthService
from app.modules.sessions.service import ShopSessionService
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.product_data_connector import DouyinProductDataConnector
from app.platforms.exceptions import PlatformAuthenticationInvalidError


class ProductDataStoredSessionIO:
    def __init__(self, session_factory, settings, *, connector=None, cipher_factory=get_secret_cipher):
        self.session_factory = session_factory
        self.settings = settings
        self.connector = connector or DouyinProductDataConnector()
        self.cipher_factory = cipher_factory

    def _accessor(self, session):
        try:
            return ShopSessionAccessor(session, self.cipher_factory())
        except EncryptionConfigurationError:
            raise SessionEncryptionUnavailableError() from None

    def page(self, generation_id, lease_id, page_no):
        with self.session_factory() as session:
            service = ProductDataService(session, settings=self.settings)
            context = service.prepare_execution(generation_id, lease_id)
            metadata = ShopSessionService(session).get_metadata(context.scope.shop_id)
            if not metadata.configured:
                raise ShopSessionNotConfiguredError()
            if metadata.status == ShopSessionStatus.INVALID:
                raise ShopSessionAuthenticationInvalidError()
            now = service.repository.now()
            # The first milestone deliberately performs no hidden identity call.
            # A stale/captured session is not proof of invalid authentication.
            if (metadata.status != ShopSessionStatus.VALID or metadata.validated_at is None
                    or not now - timedelta(seconds=self.settings.shop_session_validation_freshness_seconds)
                    <= metadata.validated_at <= now):
                raise ProductDataSessionValidationRequiredError()
            auth = self._accessor(session).get_auth_context(context.scope.shop_id, ShopPlatform.DOUYIN)
        # All DB resources have been released before HTTP/Signer work starts.
        try:
            result = self.connector.page(auth, context.scope, context.platform_shop_id, page_no)
        except PlatformAuthenticationInvalidError:
            with self.session_factory() as session:
                ProductDataService(session, settings=self.settings).prepare_execution(generation_id, lease_id)
                self._accessor(session).mark_validation_status(auth.shop_id, auth.session_version, ShopSessionStatus.INVALID)
            raise
        with self.session_factory() as session:
            service = ProductDataService(session, settings=self.settings)
            current = service.prepare_execution(generation_id, lease_id)
            if current != context:
                raise SessionVersionConflictError()
            metadata = ShopSessionService(session).get_metadata(auth.shop_id)
            if metadata.version != auth.session_version:
                raise SessionVersionConflictError()
            accessor = self._accessor(session)
            ShopSessionHealthService(session, accessor, {}, settings=self.settings,
                session_service=ShopSessionService(session, cipher=accessor.cipher)).apply_response_cookie_updates(
                auth, result.cookie_updates,
            )
        return result.page
