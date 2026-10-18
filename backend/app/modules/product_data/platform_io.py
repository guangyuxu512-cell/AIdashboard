"""Short Session transactions around, never across, a bounded platform page."""

from app.core.security import EncryptionConfigurationError, get_secret_cipher
from app.modules.product_data.service import ProductDataService
from app.modules.sessions.auth_context import ShopSessionAccessor
from app.modules.sessions.collection_readiness import bind_collection_auth_context
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import (
    SessionEncryptionUnavailableError,
    SessionVersionConflictError,
)
from app.modules.sessions.health_service import ShopSessionHealthService
from app.modules.sessions.service import ShopSessionService
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.product_data_connector import DouyinProductDataConnector
from app.platforms.exceptions import PlatformAuthenticationInvalidError
from app.platforms.registry import create_platform_connectors


class ProductDataStoredSessionIO:
    def __init__(
        self,
        session_factory,
        settings,
        *,
        connector=None,
        cipher_factory=get_secret_cipher,
        health_connectors=None,
    ):
        self.session_factory = session_factory
        self.settings = settings
        self.connector = connector or DouyinProductDataConnector()
        self.cipher_factory = cipher_factory
        self.health_connectors = health_connectors

    def _accessor(self, session):
        try:
            return ShopSessionAccessor(session, self.cipher_factory())
        except EncryptionConfigurationError:
            raise SessionEncryptionUnavailableError() from None

    def page(self, generation_id, lease_id, page_no):
        with self.session_factory() as session:
            service = ProductDataService(session, settings=self.settings)
            context = service.prepare_execution(generation_id, lease_id)
            accessor = self._accessor(session)

            def finish_owned_read() -> None:
                # This adapter exclusively owns the short-lived Session. End
                # its read transaction before an authoritative identity call.
                if session.new or session.dirty or session.deleted:
                    raise RuntimeError(
                        "Product Data Session read boundary contains pending writes",
                    )
                session.rollback()

            health_service = ShopSessionHealthService(
                session,
                accessor,
                self.health_connectors
                if self.health_connectors is not None
                else create_platform_connectors(),
                session_service=ShopSessionService(session, cipher=accessor.cipher),
                settings=self.settings,
                before_platform_io=finish_owned_read,
            )
            health = health_service.check(context.scope.shop_id, force=False)
            auth = bind_collection_auth_context(
                health,
                accessor.get_auth_context(
                    context.scope.shop_id,
                    ShopPlatform.DOUYIN,
                ),
                expected_platform=ShopPlatform.DOUYIN,
            )
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
